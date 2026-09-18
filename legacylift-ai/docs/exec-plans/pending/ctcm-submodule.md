# Link `repos/ctcm` as a git submodule instead of committing 180 MB of a client corpus into this repository

**Status: PENDING — a draft, not a conforming ExecPlan.** No branch, no code. Filed 2026-09-15
after Dependabot alerts on this repository were traced to the committed copy of the CTCM corpus:
135 of 139 open alerts came from manifests under `repos/ctcm`, and neither of the two exclusions
already in place (`.github/dependabot.yml` and `.github/codeql/codeql-config.yml`) can suppress
them, because neither governs the feature that raises them.

**This file is the definitive record of its own state.** Measurements, settled decisions, open
questions and the next action live here. It is written for someone who has this repository and
this file and nothing else.

This plan must be maintained in accordance with [`docs/exec-plan.md`](../../exec-plan.md), which
defines the ExecPlan format (there is no `PLANS.md` at the repository root).

---

## Purpose / Big Picture

Today a plain `git clone` of this repository downloads a 180 MB copy of a client application that
LegacyLift only ever *reads*. That copy is 96% of the checkout by bytes and 97% of it by file
count, and because its `package-lock.json` and `.csproj` files sit on the default branch, GitHub's
dependency graph indexes them and Dependabot raises security alerts against a codebase nobody
here builds, deploys or depends on.

After this change, `repos/ctcm` is a **submodule**: a pointer to one commit of another git
repository, stored in this repository as a single line in a file called `.gitmodules` plus a
commit identifier, with none of the corpus's own files in this repository's tree. A term of art,
defined plainly: a *submodule* is a nested checkout. Git records "at this path, put
`captechconsulting/ctcm` at commit X" and nothing more; the files live in that other repository.

What someone can do after this change that they cannot do now:

* Clone this repository and get a ~8 MB checkout instead of a ~188 MB one, and choose whether to
  pull the corpus down (`git submodule update --init repos/ctcm`).
* Open the Dependabot alerts page for this repository and see only alerts against code this
  repository owns — today that is 4 alerts, all `chromadb` in
  `tools/legacylift_search/pyproject.toml`, all real.
* Know which commit of the CTCM corpus a given measurement was taken against, because the pin is
  recorded in this repository's history. Today the corpus is an undated snapshot with no
  recoverable provenance.

How to see it working, in one line each: `git clone` of a fresh copy leaves `repos/ctcm/` empty;
`git submodule update --init repos/ctcm` fills it; `gh api .../dependabot/alerts` returns no
alert whose `manifest_path` starts with `repos/`.

---

## Progress

Nothing has been done. The investigation below is complete and reproducible; the work is not
started.

- [x] (2026-09-15) Established that the noise is Dependabot **alerts**, not version updates or
      code scanning, and that no configuration file can exclude a path from it. Evidence in
      `Surprises & Discoveries`.
- [x] (2026-09-15) Dismissed the 135 `repos/` alerts as `not_used` with a comment naming the
      corpus as reference-only. This bought quiet, not a fix: new advisories against those 36
      manifests will raise new alerts.
- [x] (2026-09-15) Confirmed `repos/ctcm` is committed directly, not a submodule already: no
      `.gitmodules`, no gitlink (mode `160000`) anywhere in the index, `git submodule status`
      empty.
- [x] (2026-09-15) Located the upstream repository and confirmed its layout matches ours, so the
      path `repos/ctcm/ctcm-api` survives conversion unchanged.
- [x] (2026-09-15) Measured the corpus drift between our snapshot and upstream `main`, and found
      the 59 LegacyLift-authored files living inside `repos/ctcm` that a conversion would destroy.
- [ ] Decide the two open questions in `Decision Log` (which upstream commit to pin, and whether
      the private-submodule clone cost is acceptable). **This is the next action, and it needs a
      human.**
- [ ] Milestone 1 — relocate the 59 LegacyLift-authored files out of `repos/ctcm`.
- [ ] Milestone 2 — convert `repos/ctcm` to a submodule at the decided pin.
- [ ] Milestone 3 — update the ignore rules, the docs and the 42 files that name `repos/ctcm`.
- [ ] Milestone 4 — verify the security outcome and record the measured result here.

---

## Surprises & Discoveries

- Observation: **`.github/dependabot.yml` has no bearing on Dependabot alerts.** That file
  configures *version updates* — the pull requests Dependabot opens to bump a dependency. Alerts
  come from the **dependency graph**, which parses every supported manifest and lock file on the
  default branch, and has no path-exclusion setting at all. The `!/repos/**` entry in that file is
  therefore doing exactly what it says and nothing more.
  Evidence: `gh pr list --author "app/dependabot" --state all` returns nothing — no version-update
  PR has ever been opened — while `gh api repos/captechconsulting/legacylift-ai/dependabot/alerts`
  returned 139 open alerts, 135 of them under `repos/`. GitHub's own documentation on how the
  dependency graph finds dependencies describes only default-branch static analysis and offers no
  exclusion mechanism.

- Observation: **CodeQL's exclusion is working and was never the problem.**
  `.github/codeql/codeql-config.yml` carries `paths-ignore: repos/**` and it holds.
  Evidence: `gh api .../code-scanning/alerts?state=open` returns 2 alerts, both under
  `tools/legacylift_search/tests`, none under `repos/`.

- Observation: **The dependency graph reads only the default branch's current tree, so removing
  the manifests from `HEAD` is sufficient. No history rewrite is needed.** This matters because
  the obvious fear — "the files are in the history, so we would have to rewrite it" — is
  unfounded and would otherwise sink the whole idea.
  Evidence: GitHub documents the graph as updating "when you change a supported manifest or lock
  file on your default branch."

- Observation: **Submodule contents are not scanned, because they are not in the parent's tree.**
  A submodule is recorded as a gitlink: one commit SHA, no files. There is no `package-lock.json`
  for the graph to parse, so no alert can be raised on the parent repository.

- Observation: **The alerts already exist on the repository that owns the code, so this moves
  nothing and duplicates nothing.** `captechconsulting/ctcm` has Dependabot alerts enabled and
  **133 open alerts** of its own. Our 135 were a second copy of substantially the same findings,
  raised against a repository that cannot act on them.
  Evidence: `gh api repos/captechconsulting/ctcm/dependabot/alerts` paginated to 98 + 31 + 4.

- Observation: **The corpus is 96% of this repository's checkout.**
  Evidence: `git ls-tree -r -l HEAD repos/ctcm` sums to **179.9 MB across 12,715 files**, against
  **188.0 MB across 13,075 files** for the whole tree. Per unit: `ctcm-api` 5,013 files,
  `ctcm-db` 3,508, `ctcm-web` 4,194.

- Observation: **The upstream repository's layout maps onto ours exactly, one submodule covers all
  three units, and no path changes.** `captechconsulting/ctcm` (private, default branch `main`,
  ~84 MB) has `ctcm-api`, `ctcm-db` and `ctcm-web` at its root, so a submodule mounted at
  `repos/ctcm` keeps `repos/ctcm/ctcm-api` — the path 42 tracked files name — byte-identical as a
  *path*. Upstream also carries `ctcm-iac`, `ctcm-perf` and `docs`, which we would newly acquire;
  they are harmless but they are not nothing, and they are not currently in scope for any plan.

- Observation: **Our snapshot is an older, smaller copy of upstream, not a different lineage.**
  Shared files mostly match byte-for-byte; where upstream has moved on, it differs.
  Evidence: comparing git blob SHAs (identical hashing on both sides, so equality is exact) —
  `ctcm-api/CLAUDE.md`, `ctcm-web/package.json` and `ctcm-web/package-lock.json` are **identical**;
  `ctcm-api/src/CTCM.API/CTCM.API.EdiService/CTCM.API.EdiService.csproj` **differs** (ours
  `9fb957ea`, upstream `c42c6de1`) — and that file is one of the two `.csproj` files that raised
  alerts, so the difference is plausibly the very dependency bump. File counts, ours versus
  upstream `main`: `ctcm-api` 4,954 / 5,596, `ctcm-db` 3,508 / 4,542, `ctcm-web` 4,194 / 4,684.

- Observation: **59 files inside `repos/ctcm` are ours, not the client's, and a naive conversion
  deletes them.** They do not exist upstream and cannot be recovered from it.
  Evidence: `repos/ctcm/ctcm-api/legacylift-docs/context/index.json` plus 57 fact-graph packs
  under `legacylift-docs/context/packs/`, and `repos/ctcm/ctcm-api/semantic-search.manifest.json`.
  The packs are cited as a measurement: the tracked-pack count is the check for what the
  `fact-graph` skill actually emitted.

- Observation: **Nothing in the code depends on the corpus being present.** The only references
  under `tools/` are three docstrings and comments describing the *shape* of the path (no
  `legacy/` parent, so the index falls back into the checkout), not code that opens it.
  Evidence: `git grep -n "repos/ctcm" -- 'tools/**'` returns
  `extract_worker.py:5`, `tests/test_config.py:275`, `tests/test_reset_guard.py:96`, all prose.
  The suite uses `tmp_path` fixtures throughout.

- Observation: **CI is unaffected.** `.github/workflows/tests.yml` uses `actions/checkout@v4` with
  no `submodules:` key, and the default is not to fetch submodules — so the job keeps working
  without change, and keeps not needing the corpus.

---

## Decision Log

- Decision: Treat the 135 dismissals as a stopgap, not the fix, and file this plan.
  Rationale: dismissal does not stop the next advisory. The 36 manifests stay in the dependency
  graph for as long as they are on the default branch, so the cleanup recurs indefinitely.
  Date/Author: 2026-09-15, Darrell Norton with Claude.

- Decision: Prefer a submodule over untracking the corpus outright.
  Rationale: both remove the manifests from the default branch and both solve the alerts. A
  submodule additionally pins *which* commit of the corpus a measurement was taken against, and
  keeps a one-command path (`git submodule update --init`) to obtain it. Untracking leaves the
  next contributor to find and clone it by hand with no recorded provenance.
  Date/Author: 2026-09-15, Darrell Norton with Claude.

- **OPEN QUESTION 1 — which commit to pin.** Upstream `main` is currently
  `a38669ee00332f14918c2fb0387612e51b78463f` (2026-09-15, "Merge pull request #180 from
  captechconsulting/bug/removing-files"). Pinning there is simple but **changes the corpus**:
  ctcm-api gains 642 files, ctcm-db 1,034, ctcm-web 490 relative to our snapshot. That matters
  because `repos/ctcm/ctcm-api` is the reference corpus behind measurements recorded in other
  plans, and a number taken against 4,954 files is not comparable to one taken against 5,596.
  The two candidate answers:
  1. **Pin upstream `main` and re-baseline.** Honest and simple; costs a re-measurement pass, and
     every existing ctcm figure needs a note saying which corpus it describes.
  2. **Find the upstream commit whose tree matches our snapshot and pin that.** Preserves
     byte-identity, so no figure moves. Feasible — the snapshot looks like a straight older copy,
     not an edited one — but it requires walking upstream history for the commit where the
     differing files last matched ours, and it may not exist as a single commit if the copy was
     ever partial.
  A third option, pushing our snapshot to upstream as a tag, is **not** recommended: it writes our
  working copy into the client's repository to solve our problem.
  Recommendation: option 2 if a matching commit is found within a reasonable search, option 1
  otherwise, with the re-baseline scoped as its own milestone.

- **OPEN QUESTION 2 — is the private-submodule clone cost acceptable?**
  `captechconsulting/ctcm` is private. A submodule of a private repository requires the cloner to
  have access to *both* repositories, and `git submodule update --init` will prompt or fail
  without credentials. Today anyone who can clone this repository gets the corpus automatically.
  After the change, someone with access to this repository but not to `ctcm` gets an empty
  directory and an error they have to interpret. This is a team-access question, not a technical
  one, and it should be answered before Milestone 2, not discovered during it.

---

## Outcomes & Retrospective

Not started, so there is no outcome to record. What "success" will mean, stated now so it cannot
be quietly redefined later: a fresh clone of this repository is under 10 MB, `repos/ctcm/ctcm-api`
still resolves to the CTCM API after one documented command, the Dependabot alert list for this
repository contains only alerts against paths this repository owns, and the full
`legacylift-search` suite is still green.

---

## Context and Orientation

This repository, `captechconsulting/legacylift-ai`, holds LegacyLift: tooling that reads legacy
codebases and produces documentation, requirements and modernization plans. It never writes the
code it analyzes. Under `repos/` it keeps sample codebases used to develop and validate that
tooling — they are *inputs to development*, not dependencies of the product.

The relevant paths, all repository-relative:

* `repos/ctcm/ctcm-api` — a C#/.NET REST API. The reference corpus for most skill work.
* `repos/ctcm/ctcm-db` — a SQL Server database project.
* `repos/ctcm/ctcm-web` — an Angular/TypeScript front end. Its `package-lock.json` alone raised
  **133** of the 135 alerts.
* `repos/nng-app-legacylift-analysis/` — a second, larger corpus, **already gitignored in full**
  at `.gitignore:109`. This is the precedent: a fresh clone has `repos/ctcm` and nothing else.
* `.github/dependabot.yml` — version-update config. Lists `pip` and `npm`, each with
  `directories: ["/**", "!/repos/**"]`.
* `.github/codeql/codeql-config.yml` — four lines, `paths-ignore: repos/**`. Working correctly.
* `.github/workflows/tests.yml` — `pytest` for `legacylift-search`, plus `dotnet build` and
  `ng build` for `platform-ui`.

Three terms used below, defined plainly:

* **Dependency graph** — GitHub's inventory of what a repository depends on, built by parsing
  manifest and lock files found on the default branch. It is not configurable by path.
* **Dependabot alerts** — security notices raised when something in the dependency graph matches
  a published advisory. Fed by the graph; unaffected by `dependabot.yml`.
* **Dependabot version updates** — the pull requests that bump a dependency. *These* are what
  `dependabot.yml` configures, and they are already silent here.

The distinction between the last two is the whole reason this plan exists: the exclusion that was
written covers the feature that was not causing trouble.

---

## Plan of Work

The work is four milestones, in order, and the first one is not optional: the 59 LegacyLift-authored
files currently inside `repos/ctcm` must leave before the directory becomes a submodule, or they are
deleted with it.

**Milestone 1 — get our own files out of the client's directory.** Move
`repos/ctcm/ctcm-api/legacylift-docs/context/` (the `index.json` and 57 fact-graph packs) and
`repos/ctcm/ctcm-api/semantic-search.manifest.json` to a location outside `repos/ctcm`. The
natural home is a sibling analysis directory — `repos/ctcm-analysis/ctcm-api/` — which mirrors the
`legacy/` + `analysis/` split the tooling already understands and keeps the two kinds of file
(client source, our output) physically separate. At the end of this milestone the packs are still
tracked, still countable, and `git ls-files repos/ctcm | grep -E "legacylift-docs|semantic-search"`
returns nothing. Anything that reads the packs by path is updated in the same commit. This
milestone is worth doing on its own merits even if the rest is abandoned: our output does not
belong inside a copy of a client's repository.

**Milestone 2 — convert the directory to a submodule.** Remove `repos/ctcm` from this
repository's index (keeping the files on disk so nothing is lost locally), then add
`captechconsulting/ctcm` as a submodule at that same path, pinned to the commit chosen in Open
Question 1. At the end, `.gitmodules` exists with one entry, `git ls-files -s repos/ctcm` shows a
single mode `160000` gitlink, and `git submodule status` names the pinned commit.

**Milestone 3 — make the repository consistent with the change.** The ignore rules at
`.gitignore:83–106` describe generated output *inside* `repos/ctcm/*`; with the corpus mounted as
a submodule, that output is the submodule's business and those patterns need review rather than
blind deletion. `CLAUDE.md`'s "Test Repositories" table must say the corpus arrives by submodule
and give the command. The 42 tracked files that name `repos/ctcm` need a pass: most are prose
examples in the plugin and in completed plans where the path is still correct and nothing changes,
but each must be confirmed, not assumed. Note that nine files under
`.claude/skills/code-modernization/` are Apache-2.0 from Anthropic and take a CapTech modification
line when touched — see `CLAUDE.md`. At the end the suite is green and a novice following
`CLAUDE.md` alone can obtain the corpus.

**Milestone 4 — prove the security outcome.** After the change lands on `main`, confirm the
dependency graph has dropped the manifests and no `repos/` alert can be raised, then record the
measured result in `Outcomes & Retrospective`. This milestone exists because the entire
justification is a security-surface claim, and an unverified security claim is worth nothing.

---

## Concrete Steps

Run everything from the repository root, `C:\Users\dnorton\captechdev\legacylift-ai` (paths below
are repository-relative and the commands are shown in POSIX shell form). Start on a branch:

    git switch -c feature/ctcm-submodule

**Before anything else, re-verify the two facts the plan rests on.** Both are cheap, and both
would invalidate the plan if they had changed:

    git ls-files -s | awk '$1=="160000"'          # expect: no output (not already a submodule)
    gh api repos/captechconsulting/ctcm -q .default_branch   # expect: main

**Milestone 1.** Move our files out, with git tracking the rename:

    mkdir -p repos/ctcm-analysis/ctcm-api
    git mv repos/ctcm/ctcm-api/legacylift-docs/context repos/ctcm-analysis/ctcm-api/context
    git mv repos/ctcm/ctcm-api/semantic-search.manifest.json repos/ctcm-analysis/ctcm-api/
    git ls-files repos/ctcm | grep -E "legacylift-docs|semantic-search" | wc -l

The last command must print `0`. Confirm the packs survived the move:

    ls repos/ctcm-analysis/ctcm-api/context/packs/*.pack.json | wc -l     # expect 57

Then find and fix anything that read them at the old path:

    git grep -ln "legacylift-docs/context" -- . | grep -v '^repos/'

Commit before going further.

**Milestone 2.** Take the corpus out of this repository's index without deleting the working
copy, which is what `--cached` means here:

    git rm -r --cached repos/ctcm --quiet
    git status --short | head -5

Git now reports thousands of deletions staged and the files still on disk. Move the local copy
aside — do not delete it until the submodule is verified — and add the submodule:

    mv repos/ctcm repos/ctcm.local-backup
    git submodule add --name ctcm https://github.com/captechconsulting/ctcm.git repos/ctcm
    cd repos/ctcm && git checkout <PINNED-SHA> && cd ../..
    git add .gitmodules repos/ctcm

Verify the shape before committing:

    cat .gitmodules
    git ls-files -s repos/ctcm          # expect one line, mode 160000
    git submodule status                # expect the pinned SHA at repos/ctcm
    ls repos/ctcm/ctcm-api/src          # expect CTCM.API (the path still resolves)

Commit, then delete `repos/ctcm.local-backup` only once Milestone 4 has passed.

**Milestone 3.** Work through the consistency pass:

    sed -n '80,110p' .gitignore         # review the repos/ctcm/* output patterns
    git grep -ln "repos/ctcm" -- . | grep -v '^repos/' | wc -l    # expect 42 to review

Then run the suite from its own directory, because `pytest` is configured there:

    cd tools/legacylift_search && pytest -q --durations=25

**Milestone 4.** After the merge to `main`, allow a few minutes for the graph to rebuild, then:

    gh api repos/captechconsulting/legacylift-ai/dependabot/alerts --paginate \
      --jq '.[] | select(.state=="open") | .dependency.manifest_path' | sort | uniq -c

---

## Validation and Acceptance

Acceptance is four observable behaviors, each with the command that shows it and the output to
expect.

**A fresh clone is small and the corpus is absent.** In a scratch directory:

    git clone https://github.com/captechconsulting/legacylift-ai.git probe
    du -sh probe                        # expect under 10 MB, against ~188 MB today
    ls probe/repos/ctcm                 # expect an empty directory

**One documented command brings the corpus back, at a known commit.**

    cd probe && git submodule update --init repos/ctcm
    ls repos/ctcm/ctcm-api/src/CTCM.API | head -3
    git submodule status                # the SHA printed here is the corpus provenance

**No Dependabot alert names a path under `repos/`.** Run the Milestone 4 command above. Every
line of output must be a path this repository owns. Today's expected output is the four
`tools/legacylift_search/pyproject.toml` alerts and nothing else; if new advisories have landed
against `tools/` or `platform-ui/` since, those are legitimate and count as a pass.

**The suite is still green.** From `tools/legacylift_search`, `pytest -q` exits 0. The baseline at
the time of writing is 1,280 tests across 64 modules; the count may have grown, and the
requirement is that it passes, not that it matches. No test touches `repos/`, so a failure here
means something in Milestone 1 or 3 went wrong, not the submodule itself.

**The negative test that proves the mechanism.** Before the change, `git ls-files
repos/ctcm/ctcm-web/package-lock.json` prints that path — which is why the graph indexes it.
After, the same command prints nothing while `ls repos/ctcm/ctcm-web/package-lock.json` still
finds the file on disk. That pair is the whole change in two commands: present to the developer,
invisible to the default branch.

---

## Idempotence and Recovery

Milestone 1 is a `git mv` and is safe to repeat: run it twice and the second run fails with
"bad source", having changed nothing.

Milestone 2 is the risky one, and the risk is losing the local corpus. `git rm -r --cached` does
not touch the working tree — that is the entire point of `--cached` — and the plan renames the
directory to `repos/ctcm.local-backup` rather than deleting it, so a mistake costs a `mv` back:

    git reset HEAD -- repos/ctcm ; rm -rf repos/ctcm ; mv repos/ctcm.local-backup repos/ctcm

If `git submodule add` fails halfway it can leave a stale entry in `.git/modules/ctcm` that makes
the next attempt fail with "already exists in the index". Clear it and retry:

    git submodule deinit -f repos/ctcm ; rm -rf .git/modules/ctcm ; git rm -f repos/ctcm

The whole branch is discardable until it merges: `git switch main && git branch -D
feature/ctcm-submodule` restores the status quo, because nothing outside this repository is
modified. Nothing in this plan writes to `captechconsulting/ctcm`, and nothing in it rewrites
history.

The one genuinely irreversible step is the merge to `main`, and even that is recoverable by
reverting the commit: the corpus returns to the tree and the alerts return with it.

---

## Artifacts and Notes

The measurement that opened this, reproduced in full so it can be re-run:

    $ gh api repos/captechconsulting/legacylift-ai/dependabot/alerts --paginate \
        --jq '.[] | select(.state=="open") | .dependency.manifest_path' | sort | uniq -c
        133 repos/ctcm/ctcm-web/package-lock.json
          4 tools/legacylift_search/pyproject.toml
          1 repos/ctcm/ctcm-api/src/CTCM.API/ServiceDefaults/ServiceDefaults.csproj
          1 repos/ctcm/ctcm-api/src/CTCM.API/CTCM.API.EdiService/CTCM.API.EdiService.csproj

The same command after the 135 dismissals on 2026-09-15:

    $ gh api ... | sort | uniq -c
          4 tools/legacylift_search/pyproject.toml

The weight of the corpus:

    $ git ls-tree -r -l HEAD repos/ctcm | awk '{s+=$4} END {printf "%.1f MB / %d files\n", s/1048576, NR}'
    179.9 MB / 12715 files
    $ git ls-tree -r -l HEAD | awk '{s+=$4} END {printf "%.1f MB / %d files\n", s/1048576, NR}'
    188.0 MB / 13075 files

Proof that it is not already a submodule:

    $ git ls-files -s | awk '$1=="160000"'
    $ git submodule status
    $ ls .gitmodules
    ls: cannot access '.gitmodules': No such file or directory

The four remaining alerts are all `chromadb` — two critical, two high — against
`tools/legacylift_search/pyproject.toml`. They are accurate and they are ours: the pin is
deliberate, so they should stay visible and be resolved on their own merits, not swept up by this
work.

---

## Interfaces and Dependencies

No code interface changes. The contract this plan alters is a *repository layout* contract, and it
has exactly three surfaces.

`.gitmodules`, at the repository root, must exist at the end of Milestone 2 with one entry and no
others:

    [submodule "ctcm"]
        path = repos/ctcm
        url = https://github.com/captechconsulting/ctcm.git

The path `repos/ctcm/{ctcm-api,ctcm-db,ctcm-web}` must continue to resolve to the same three units
after `git submodule update --init`. This is a hard requirement, not a preference: 42 tracked
files name those paths, including prose in the `code-modernization` plugin and figures in active
ExecPlans, and the plan's value depends on none of them needing to change.

`CLAUDE.md`'s "Test Repositories" section is the only place a newcomer learns the corpus exists,
so it must state that `repos/ctcm` is a submodule, give
`git submodule update --init repos/ctcm`, and say that a plain clone leaves it empty. The existing
note that `repos/nng-app-legacylift-analysis/` is gitignored in full stays true and sits naturally
beside it.

Tooling assumed available: `git` 2.13 or newer (for `git submodule` with `--name`), and the `gh`
CLI authenticated against `captechconsulting` for the alert verification in Milestone 4. No new
Python or Node dependency is introduced.

---

## Revision note

2026-09-15 — Created. Filed from the Dependabot investigation described in
`Surprises & Discoveries`, which established that the alerts come from the dependency graph rather
than from anything `.github/dependabot.yml` or `.github/codeql/codeql-config.yml` controls, and
that a submodule is the only configuration-level way to keep a corpus in the working tree while
keeping its manifests off the default branch. Written as a pending draft rather than an active
plan because two questions need a human answer first: which upstream commit to pin, and whether a
private submodule is acceptable for everyone who clones this repository.
