# Tests for `platform-ui` — a shipped v4 component whose only quality floor is "it compiles"

**Status: PENDING — a draft, not a conforming ExecPlan.** No branch, no code. Filed 2026-09-14 from
the pre-v4.0.0 readiness review, which found `platform-ui` shipping at `4.0.0` as one of v4's three
deployable components with **zero tests**, while the other two have a 1,264-test suite and a
documented acceptance floor.

**This file is the definitive record of its own state.** Measurements, settled decisions, open
questions and next action live here.

Related: [`pending/reqs-review-ui.md`](./reqs-review-ui.md) is the parent — Milestone 4 of the
requirements plan, of which `platform-ui` is the built read-only Milestone 1. Read
[`platform-ui/README.md`](../../../platform-ui/README.md) first for what M1 actually is; it is the
definitive record of the component. This draft covers only the test question that file and
`docs/architecture.md` §8 both name as a known gap.

---

## Purpose / Big Picture

`docs/architecture.md` §8 already states the gap plainly: *"There are **no tests** yet — the Angular
scaffold's vitest setup is what triggered the npm bug above, and Milestone 1 had no test scope.
Worth adding before the write path lands."* This draft exists so that "worth adding" is a tracked
deliverable with a measured starting point, rather than a sentence in a document nobody is assigned
to act on.

The asymmetry is the argument. `legacylift-search` cannot merge without 1,264 green tests;
`platform-ui` cannot merge without `dotnet build` and `ng build` exiting 0. Those are not comparable
bars, and the component with the weaker bar is the one a client sees.

**What this is not.** Not a demand for a coverage percentage, not a case for end-to-end browser
automation, and not a blocker on the write path's design. It is an argument that a read surface over
a requirements store has a small number of behaviours worth pinning *because they are the ones a
reviewer would silently be misled by*, and that the scaffolding to pin half of them is already
installed and idle.

---

## The measurement that motivates the work

Measured 2026-09-14 at `f5c4b8ac`:

| | API | Web |
|---|---|---|
| Source | 948 lines of C# in 4 files (`Program.cs` 215, `Data/Requirements.cs` 595, `Data/Catalog.cs` 79, `Data/Store.cs` 59) | 23 TypeScript files under `src/app` — 11 page components, 4 shared components, `core/api.ts`, `core/models.ts` |
| Test project / spec files | none — there is no `*.Tests.csproj` in the repository | none — zero `*.spec.ts` |
| CI gate | `dotnet build platform-ui/api --nologo` | `npm ci --legacy-peer-deps && npm run build` |

**The web test scaffold is already complete and idle.** `package.json` declares `"test": "ng test"`,
`vitest` ^4.0.8 and `jsdom` are installed as devDependencies, and `tsconfig.spec.json` exists with
`types: ["vitest/globals"]` and an `include` of `src/**/*.spec.ts`. Every piece is present except the
spec files. So the first web test costs approximately nothing to stand up — which materially changes
the cost side of this argument and is the main reason the draft is worth opening now.

The API has no equivalent: a test project must be created, referenced and added to CI.

`Data/Requirements.cs` at 595 lines is 63% of the API and holds the server-side paging, FTS5 search,
facets and sort behind `…/requirements` — the densest piece of untested logic in the component, and
the one whose failure modes are quietest.

---

## Decisions already settled

- **Decision: the bar is "a wrong answer is caught", not a coverage number.** This component's
  failure mode is not a crash — a crash is visible. It is a requirements list that silently returns
  the wrong page, a facet count that disagrees with the rows it summarises, a citation snippet that
  resolves to the wrong lines, or a system with no `gr` tables rendering as a system with no
  requirements.
  Rationale: the point of Layer 1 is that a reviewer's judgement is trustworthy. A read surface that
  quietly misreports is worse than one that is down, because only one of those states is noticed.

- **Decision: `prepare_data.py` is in scope, and is the cheapest win.** It is Python, the repository
  already runs pytest for exactly that, and its 2026-09-14 change (`--stale-docs-root`, the declared
  `SYSTEMS`/`PROJECT` constants) was verified by a manual "identical output, 379/383 citations
  resolved" comparison that nothing re-runs.
  Rationale: a one-off manual verification of a data-preparation script is a regression waiting to
  happen, and this is the only part of the component already sitting in a tested language.

- **Decision: no browser automation in the first pass.** Component tests through the installed
  vitest + jsdom setup only.
  Rationale: Playwright would need the API, a prepared `data/` snapshot and a served build — three
  moving parts, to catch a class of defect the component tests have not yet been given a chance to
  catch.

---

## Open questions — these need a design conversation, which is why this is a draft

1. **Does the API get a test project, or contract tests from outside?** An xunit project against a
   fixture SQLite store is conventional and tests the C# directly. The alternative is to test the
   HTTP contract from the Python side against the same fixture, which would also pin the shape the
   Angular client depends on. The second is unusual; it is raised only because this repository
   already has the harness for it, and because the contract — not the C# — is what the web half
   consumes.

2. **What is the fixture store?** The real `data/` snapshot is gitignored, client-derived, and must
   stay that way, so a committed fixture `knowledge.sqlite` has to be *synthesised*. That is the
   same question `legacylift-search`'s own fixtures already answered, and the answer should probably
   be the same mechanism rather than a second one. Read what `tools/legacylift_search/tests/` builds
   before inventing a fixture format.

3. **Does `ng test` join CI in the same change, or only once the first spec lands?** A `test` job
   that passes because it found no tests is precisely the failure mode this draft exists to end.
   Vitest's behaviour on an empty suite must be checked and pinned — `--passWithNoTests` must not be
   set.

4. **Is the write path close enough that this should wait for it?** `pending/reqs-review-ui.md`
   records that everything past read-only is blocked on the reviewer-identity question `set_state`
   forces. If the write path lands soon, tests written against the read surface may be rewritten
   with it. The counter-argument is that the write path is the half that must not land untested, so
   the harness should exist before it, not after.

5. **What does "the API returned the wrong page" look like as an assertion?** Server-side paging over
   FTS5 with facets and sort has an ordering-stability question inside it: two rows of equal rank
   with no tiebreak can swap between pages, losing or duplicating a row across a reviewer's
   pagination. Check whether `Data/Requirements.cs` has a deterministic tiebreak before writing a
   test that assumes one — if it does not, that is a finding, not a test-design problem.

---

## Interfaces and Dependencies

- `platform-ui/api/Data/Requirements.cs` — paging, FTS5 search, facets, sort. The density argument
  above, and open question 5.
- `platform-ui/api/Data/Store.cs` — how a system with no `gr` tables is detected. `architecture.md`
  §8 asserts this "correctly disables its Requirements nav"; nothing tests it.
- `platform-ui/web/package.json`, `platform-ui/web/tsconfig.spec.json` — the idle vitest scaffold.
  Note that installing here requires `--legacy-peer-deps` because npm's peer resolver crashes on
  vitest 4's peer graph; that is documented current state, not something to fix as part of this.
- `platform-ui/tools/prepare_data.py` — the Python half, and the cheapest test to write.
- `.github/workflows/tests.yml` — the `platform-ui` job, which today builds and does not test.
- `docs/architecture.md` §8 *Known gaps* and §9 *Continuous integration* — both state the current
  position and must be updated by whatever change closes this.
