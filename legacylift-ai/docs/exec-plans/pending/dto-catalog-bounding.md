# Bounding the DTO catalog — an unbounded response and a silent rule truncation

**Status: PENDING — a draft, not a conforming ExecPlan.** No branch, no code. Written 2026-09-10
from two defects the four-round NNG extraction exposed in the Data objects phase of
`.claude/skills/code-modernization/workflows/extract-rules.js`. Promoted out of
[`deferred-small-items.md`](./deferred-small-items.md) entry 14 (number retired, not reused) because
the fix needs a design choice about what a bounded catalog *is*, and the entry bar there is
"measured, and no design question attached."

**This file is the definitive record of its own state.** Measurements, settled decisions, open
questions and next action live here, not in the requirements plan that found them.

**Partial mitigation shipped 2026-09-14 (defect 2 disclosed, NOT fixed).** The pre-v4.0.0 review
ruled that a v4 deliverable must not report 56.5% completeness as if it were finished, so the
truncation is now *measured and disclosed* rather than silent: `extract-rules.js` names the cap
(`DTO_RULE_NAME_CAP`), computes how many rule names the agent actually saw, and returns
`dataObjectsCoverage {rulesShown, rulesTotal, ruleNameCap, truncated}`; `/modernize-extract-rules`
step 5 renders an admonition from it, and Method B — which has no measurement to render — states its
basis instead. **Nothing about the cap or the response bound changed**, so both defects below are
open exactly as written and this draft is still the work. Two consequences for whoever picks it up:
the disclosure is now a contract two readers depend on, so a batching design must keep
`dataObjectsCoverage` meaningful (with batching, `truncated` should become `false`, not disappear),
and the admonition text in the command is the thing to delete when it does.

Related: [`active/reqs-to-data-store.md`](../active/reqs-to-data-store.md) →
`Surprises & Discoveries` → *What the four-round run discovered (2026-09-10)*, which records these
two findings as part of that run and points here. `deferred-small-items.md` **entry 13** is a
different defect in the same file (the extractor emitting prose into `source`) — whoever opens
`extract-rules.js` should look at both, and remember the CapTech attribution line that `CLAUDE.md`
requires be *overwritten*, not appended.

---

## Purpose / Big Picture

The last phase of `/modernize-extract-rules` asks one agent to catalog the system's data transfer
objects and to say which mined business rules read or produce each. The calling session renders
`DATA_OBJECTS.md` from that return value. Two things are wrong with how it is asked:

1. **The response is unbounded**, so a large enough estate produces output no single tool call can
   carry. It failed once in three runs, on the largest.
2. **The input is silently truncated** at 250 rule names, so past 250 rules the catalog's
   `consumedBy` cross-references are incomplete *and look complete*.

The second is the more damaging one and the less visible. The first announces itself in a log; the
second is already sitting in the corpus of record.

**What this is not.** Not a change to rule mining, verification, or the P0 panel — those phases are
finished and measured, and nothing here touches them. Not a requirements-store change:
`dataObjects` is never ingested, so no Milestone of the requirements plan depends on this. And **not
a schema-size fix** — see the next section, which exists specifically to stop that.

---

## What this is NOT: the `RULES_SCHEMA` defect

Recorded first because the symptom is misleading and the wrong fix is the obvious one. Both failures
report "payload too large"; they have opposite causes.

| | `RULES_SCHEMA`, fixed 2026-09-08 | `DTO_SCHEMA`, this draft |
|---|---|---|
| what was too large | **the schema** — 15,242 bytes of JSON | **the response** — the schema is 543 bytes |
| where it failed | at **spawn**, before the agent ran | at `StructuredOutput`, after the agent had the answer |
| the message | `blocked by safety classifier: output schema too large to classify safely` | `1 StructuredOutput validation failure (last input: {"__unparsedToolInput":{"raw":...` |
| blast radius | **every mining agent**; no live extraction possible for six days | one agent, retried successfully, null-tolerant downstream |
| the fix | shrink the schema (guidance moved into `NOTATION`) | bound the response |

Serialized sizes of every schema in the file, measured 2026-09-10:

    RULES_SCHEMA      2239 bytes   (post-fix; was 15,242)
    COVERAGE_SCHEMA    698 bytes
    DTO_SCHEMA         543 bytes   <- the one that stalled
    VERDICT_SCHEMA     496 bytes
    P0_SCHEMA          340 bytes

**`DTO_SCHEMA` is the second-smallest schema in the file.** Shrinking it accomplishes nothing. It
stalled *because* it is small: it constrains shape and constrains no quantity.

---

## Defect 1 — the response is unbounded

`DTO_SCHEMA` declares `dataObjects` as an open array whose items each carry an open `fields` array
and an open `consumedBy` array of rule-name strings. The prompt states no limit on any of the three.
Nothing caps how much the agent may return, so the ceiling is whatever the tool-input limit happens
to be.

Measured across three runs (`dataObjects` payload as serialized JSON):

| run | rules in | data objects | fields | consumedBy links | payload | first attempt |
|---|---|---|---|---|---|---|
| round 1 (2026-09-08) | 133 | 62 | 505 | 317 | 72,024 B | succeeded |
| scoped 2-round (2026-09-09) | 186 | 73 | 498 | 475 | 93,472 B | succeeded |
| **four-round (2026-09-10)** | **437** | **63** | **543** | **535** | **99,924 B** | **stalled, retry succeeded** |

The failing run's own transcript states the cause twice in plain words — *"The payload was too
large. Let me submit a more compact catalog."* — before it gave up and the runtime's retry produced
the 99,924-byte catalog above. **So ~100 KB is near the ceiling and the first attempt was larger
than what eventually landed**; the retry succeeded by being more compact, not by being luckier.

**Why it cost nothing this time, and why that is luck.** The phase is a single `await agent(...)`
consumed as `dataObjects: (dto && dto.dataObjects) || []`, and it runs *after* `confirmed` is
computed — so a null catalog degrades the return value and cannot abort the run or lose rules. Had
this schema shape sat on the mining or referee agents, four rounds of work would have been at risk.

**It scales with the estate rather than being flaky.** It failed on the largest of three runs and
not on the two smaller ones. `consumedBy` is the term that grows with the rule corpus: 317 → 475 →
535 links as rules went 133 → 186 → 437.

---

## Defect 2 — the input is truncated at 250 rules, silently

The prompt passes the rule list through `ruleNames.slice(0, 250)` — a hard slice, with no cap stated
to the agent and no log line saying anything was withheld. **The four-round run had 437 confirmed
rules, so 187 were never shown to the DTO agent at all**, and `consumedBy` cannot name a rule the
agent never saw.

**This is measured, not inferred.** Testing every distinct `consumedBy` name in each saved corpus
against the rule list, split at the slice boundary:

| run | rules | distinct rules named in `consumedBy` | within first 250 | **beyond 250** | unmatched | rule coverage |
|---|---|---|---|---|---|---|
| round 1 | 133 | 133 | 133 | — | 0 | **100%** |
| scoped 2-round | 186 | 186 | 186 | — | 0 | **100%** |
| four-round | 437 | 247 | **247** | **0** | 0 | **56.5%** |

**The two runs below the cap referenced every single rule they were given.** The run above it
referenced 247 of the 250 it could see and **0 of the 187 it could not**. The agent's behavior is
consistent across all three; the slice is the whole difference. There is also **not one unmatched
name in any run**, so name-matching is not a confounder.

**Why this is worse than the stall.** The stall is loud, self-recovering, and leaves a log line.
This produces a catalog that looks complete: 63 objects, 535 links, no warning, no error, exit 0.
A reader of `DATA_OBJECTS.md` has no way to know that 43% of the mined rules were structurally
incapable of appearing in it. It became reachable only now because no earlier run exceeded 250
rules — round 1 and the scoped run were both comfortably under, which is exactly why their 100%
coverage looks like evidence that the phase works.

---

## Decisions already settled

1. **Do not shrink `DTO_SCHEMA`.** It is 543 bytes. The size problem is the response. Recorded as a
   table above so this cannot be re-proposed from the symptom.
2. **Do not touch the mining, verify or P0 phases.** They are finished and measured; this is the
   last phase and is independent of them.
3. **Nothing here blocks the requirements store.** `dataObjects` is not ingested and no `gr*` table
   reads it, so this is not a Milestone 1 or 1.5 dependency and must not be sequenced ahead of them.
4. **The null-tolerant consumption stays.** `(dto && dto.dataObjects) || []` is correct and is why
   the stall was survivable; a fix must not make a failed catalog fatal to the run.
5. **The corpora are not to be regenerated for this.** Each extraction is hours of model time in a
   gitignored tree. A fix is verified on the *next* run, or on a cheap synthetic case — never by
   re-mining NNG.

---

## Open questions — these need a design conversation, which is why this is a draft

1. **What bounds the response?** A stated object cap in the prompt (three runs produced 62–73, so
   ~80 would not bind in practice), a `maxItems` on the schema array, or both? Note `maxItems`
   bounds the array but **not** the per-object `fields` and `consumedBy` lists, so the prompt cap is
   the load-bearing half and the schema constraint is at best a backstop.
2. **Does `consumedBy` need to be a name list at all?** It is the term that grows with the rule
   corpus. A count, or an id list, or moving the linkage to the *rule* side (each rule naming the
   objects it touches, which the mining agent already has in context) would each remove the growth
   term — but the third changes what the mining agents are asked for, which contradicts settled
   decision 2. Which of these is wanted is the central design question here.
3. **How should the rule list be delivered past 250?** Page the catalog over the rule list and merge
   the results, hand the agent a rule *index* to search rather than an inline list, or leave the cap
   and log what was withheld? Paging multiplies the agents; logging is honest but leaves the output
   incomplete.
4. **Is an incomplete `consumedBy` acceptable if it is disclosed?** If yes, this is a one-line
   logging fix plus a note in `DATA_OBJECTS.md`. If no, it is question 3's paging work. This is the
   cheapest decision available and it changes the size of the job by an order of magnitude — decide
   it first.
5. **Should the phase fail loudly rather than degrade?** Today a null catalog silently yields `[]`.
   A run that produced no data objects is arguably a defect worth surfacing in the return value's
   `stats`, without making it fatal (decision 4).

---

## Why it was deferred

Found mid-measurement on a run whose numbers it does not affect, in a phase nothing downstream of
the requirements store reads. The retry recovered the catalog, so the four-round corpus has a usable
`dataObjects` block — incomplete in `consumedBy`, and now documented as such. Fixing it during the
run would have meant re-running the Data objects phase to verify, against a corpus that must not be
regenerated.

---

## Interfaces and Dependencies

**Would touch,** all in `.claude/skills/code-modernization/workflows/extract-rules.js`, Data objects
phase only:

- `DTO_SCHEMA` — only if question 1 settles on a schema-side backstop.
- The `dto-catalog` agent prompt — the object cap, and the `ruleNames.slice(0, 250)` call.
- Possibly the returned `stats` block, for question 5.

**Verification without re-mining.** The truncation test in this draft is reproducible against any
saved corpus: parse `confirmedRules`, split the names at the cap, and check whether any
`consumedBy` entry falls beyond it. On a fixed corpus that is a pure function of the saved JSON, so
it is a unit test rather than a run. The stall is harder to pin cheaply — the honest check is the
payload size of the returned catalog against the ~100 KB observation above.

**Attribution.** `.claude/skills/code-modernization/` is Apache 2.0 by Anthropic. Per `CLAUDE.md`,
overwrite the existing `Modified by CapTech on [date]: ...` line at the top of the file — do not
append a second one.
