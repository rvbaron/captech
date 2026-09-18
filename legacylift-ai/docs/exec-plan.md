# Claude Execution Plans (ExecPlans):

This document describes the requirements for an execution plan ("ExecPlan"), a design document that a coding agent can follow to deliver a working feature or system change. Treat the reader as a complete beginner to this repository: they have only the current working tree and the single ExecPlan file you provide. There is no memory of prior plans and no external context.

## How to use ExecPlans

**There is no `PLANS.md` in this repository — this file replaced it.** Where other projects say "follow PLANS.md", follow *this* document to the letter; if it is not in your context, read it in full before authoring. Be thorough in reading (and re-reading) source material to produce an accurate specification. When creating a spec, start from the skeleton and flesh it out as you do your research.

When implementing an executable specification (ExecPlan), do not prompt the user for "next steps"; simply proceed to the next milestone. Keep all sections up to date, add or split entries in the list at every stopping point to affirmatively state the progress made and next steps. Resolve ambiguities autonomously, and commit frequently.

When discussing an executable specification (ExecPlan), record decisions in a log in the spec for posterity; it should be unambiguously clear why any change to the specification was made. ExecPlans are living documents, and it should always be possible to restart from _only_ the ExecPlan and no other work.

When researching a design with challenging requirements or significant unknowns, use milestones to implement proof of concepts, "toy implementations", etc., that allow validating whether the user's proposal is feasible. Read the source code of libraries by finding or acquiring them, research deeply, and include prototypes to guide a fuller implementation.

## Requirements

NON-NEGOTIABLE REQUIREMENTS:

* Every ExecPlan must be fully self-contained. Self-contained means that in its current form it contains all knowledge and instructions needed for a novice to succeed.
* Every ExecPlan is a living document. Contributors are required to revise it as progress is made, as discoveries occur, and as design decisions are finalized. Each revision must remain fully self-contained.
* Every ExecPlan must enable a complete novice to implement the feature end-to-end without prior knowledge of this repo.
* Every ExecPlan must produce a demonstrably working behavior, not merely code changes to "meet a definition".
* Every ExecPlan must define every term of art in plain language or do not use it.

Purpose and intent come first. Begin by explaining, in a few sentences, why the work matters from a user's perspective: what someone can do after this change that they could not do before, and how to see it working. Then guide the reader through the exact steps to achieve that outcome, including what to edit, what to run, and what they should observe.

The agent executing your plan can list files, read files, search, run the project, and run tests. It does not know any prior context and cannot infer what you meant from earlier milestones. Repeat any assumption you rely on. Do not point to external blogs or docs; if knowledge is required, embed it in the plan itself in your own words. If an ExecPlan builds upon a prior ExecPlan and that file is checked in, incorporate it by reference. If it is not, you must include all relevant context from that plan.

## Formatting

Format and envelope are simple and strict. Each ExecPlan must be one single fenced code block labeled as `md` that begins and ends with triple backticks. Do not nest additional triple-backtick code fences inside; when you need to show commands, transcripts, diffs, or code, present them as indented blocks within that single fence. Use indentation for clarity rather than code fences inside an ExecPlan to avoid prematurely closing the ExecPlan's code fence. Use two newlines after every heading, use # and ## and so on, and correct syntax for ordered and unordered lists.

When writing an ExecPlan to a Markdown (.md) file where the content of the file *is only* the single ExecPlan, you should omit the triple backticks.

Write in plain prose. Prefer sentences over lists. Avoid checklists, tables, and long enumerations unless brevity would obscure meaning. Checklists are permitted only in the `Progress` section, where they are mandatory. Narrative sections must remain prose-first.

## Guidelines

Self-containment and plain language are paramount. If you introduce a phrase that is not ordinary English ("daemon", "middleware", "RPC gateway", "filter graph"), define it immediately and remind the reader how it manifests in this repository (for example, by naming the files or commands where it appears). Do not say "as defined previously" or "according to the architecture doc." Include the needed explanation here, even if you repeat yourself.

Avoid common failure modes. Do not rely on undefined jargon. Do not describe "the letter of a feature" so narrowly that the resulting code compiles but does nothing meaningful. Do not outsource key decisions to the reader. When ambiguity exists, resolve it in the plan itself and explain why you chose that path. Err on the side of over-explaining user-visible effects and under-specifying incidental implementation details.

Anchor the plan with observable outcomes. State what the user can do after implementation, the commands to run, and the outputs they should see. Acceptance should be phrased as behavior a human can verify ("after starting the server, navigating to [http://localhost:8080/health](http://localhost:8080/health) returns HTTP 200 with body OK") rather than internal attributes ("added a HealthCheck struct"). If a change is internal, explain how its impact can still be demonstrated (for example, by running tests that fail before and pass after, and by showing a scenario that uses the new behavior).

Specify repository context explicitly. Name files with full repository-relative paths, name functions and modules precisely, and describe where new files should be created. If touching multiple areas, include a short orientation paragraph that explains how those parts fit together so a novice can navigate confidently. When running commands, show the working directory and exact command line. When outcomes depend on environment, state the assumptions and provide alternatives when reasonable.

Be idempotent and safe. Write the steps so they can be run multiple times without causing damage or drift. If a step can fail halfway, include how to retry or adapt. If a migration or destructive operation is necessary, spell out backups or safe fallbacks. Prefer additive, testable changes that can be validated as you go.

Validation is not optional. Include instructions to run tests, to start the system if applicable, and to observe it doing something useful. Describe comprehensive testing for any new features or capabilities. Include expected outputs and error messages so a novice can tell success from failure. Where possible, show how to prove that the change is effective beyond compilation (for example, through a small end-to-end scenario, a CLI invocation, or an HTTP request/response transcript). State the exact test commands appropriate to the project’s toolchain and how to interpret their results.

Capture evidence. When your steps produce terminal output, short diffs, or logs, include them inside the single fenced block as indented examples. Keep them concise and focused on what proves success. If you need to include a patch, prefer file-scoped diffs or small excerpts that a reader can recreate by following your instructions rather than pasting large blobs.

## Milestones

Milestones are narrative, not bureaucracy. If you break the work into milestones, introduce each with a brief paragraph that describes the scope, what will exist at the end of the milestone that did not exist before, the commands to run, and the acceptance you expect to observe. Keep it readable as a story: goal, work, result, proof. Progress and milestones are distinct: milestones tell the story, progress tracks granular work. Both must exist. Never abbreviate a milestone merely for the sake of brevity, do not leave out details that could be crucial to a future implementation.

Each milestone must be independently verifiable and incrementally implement the overall goal of the execution plan.

## Large plans: split current state from archived detail

Long-running ExecPlans accumulate a large back-history of completed milestones, retrospectives, and build steps. Once a single plan file grows past roughly a thousand lines, that history starts to crowd out the current state: an agent (or human) opening the file has to wade through finished work to find what is live. For large efforts, split the plan into two files so the main file stays focused on the current state while nothing is lost.

The split is:

* The main plan file (for example, `docs/exec-plans/active/<name>.md`) retains everything needed to understand and continue the *current* state: the title and preamble, `Purpose / Big Picture`, the full `Progress` checklist, the living `Surprises & Discoveries` and `Decision Log` sections, a short current-status summary under `Outcomes & Retrospective`, the orientation and design narrative (`Context and Orientation`, `Plan of Work`), the active, paused, and upcoming milestones (including their `Concrete Steps`), and the `Validation and Acceptance`, `Idempotence and Recovery`, `Artifacts and Notes`, and `Interfaces and Dependencies` sections.
* A companion archive file named with an `-additional-info` suffix (for example, `docs/exec-plans/active/<name>-additional-info.md`) holds completed-milestone detail that is no longer needed to grasp the current state: the full per-milestone `Outcomes & Retrospective` entries, any multi-agent or wave dispatch plans for work already finished, and the `Concrete Steps` (build instructions) for milestones that are already shipped.

The main file must reference the archive file near the top (in the preamble) and again at each point where archived detail was lifted out (for example, a one-line pointer under `Concrete Steps` saying that the steps for completed milestones live in the archive). An agent reading the main file should not need to open the archive to continue current work; it reads the archive only when it genuinely needs historical detail, such as reconstructing why a completed milestone was built a certain way. State this expectation explicitly in both files.

Self-containment still holds, with the boundary redrawn: the main file must be self-contained for *current and future* work — a novice can read it top to bottom and continue from the present state without the archive — and the archive must be self-contained for the *history* it records. When a milestone moves from active to complete, migrate its `Concrete Steps` and write its retrospective entry into the archive, and update the main file's `Progress` and `Outcomes & Retrospective` summary to match. Keep the `Surprises & Discoveries` and `Decision Log` sections in the main file: they are living references that explain why current code looks the way it does, and they are consulted continuously rather than only as history.

## Living plans and design decisions

* ExecPlans are living documents. As you make key design decisions, update the plan to record both the decision and the thinking behind it. Record all decisions in the `Decision Log` section.
* ExecPlans must contain and maintain a `Progress` section, a `Surprises & Discoveries` section, a `Decision Log`, and an `Outcomes & Retrospective` section. These are not optional.
* When you discover optimizer behavior, performance tradeoffs, unexpected bugs, or inverse/unapply semantics that shaped your approach, capture those observations in the `Surprises & Discoveries` section with short evidence snippets (test output is ideal).
* If you change course mid-implementation, document why in the `Decision Log` and reflect the implications in `Progress`. Plans are guides for the next contributor as much as checklists for you.
* At completion of a major task or the full plan, write an `Outcomes & Retrospective` entry summarizing what was achieved, what remains, and lessons learned.

## Session handoffs

A handoff is a disposable message to the next agent, not a project artifact. It says what to do next and what not to waste a pass on; the durable facts live in the plan.

* **Location.** `docs/exec-plans/active/SESSION-HANDOFF-<topic>-<YYYY-MM-DD>.md`, regardless of which folder the plan it concerns lives in. When the work it hands off is done, move it to `docs/exec-plans/completed/` with a `DISCHARGED` banner naming the commit or finding list that discharged it.
* **Nothing about a handoff goes in `CLAUDE.md` or the plan index.** `CLAUDE.md` records what is durably true about the project; a handoff records what one session wants the next one to do. Do not add a handoff to `docs/execplans-status.md`, do not summarize it there, and do not update the index as a side effect of writing one.
* **Durable facts belong in the plan, not the handoff.** If a handoff is about to state a measurement, a decision, or a correction that will still be true after the work is done, write it to the plan's `Decision Log` or `Surprises & Discoveries` and reference it by path. A handoff that restates its plan's content will drift from it, and the paraphrase is what the next agent acts on.
* **Say what was verified and what was not.** The two most valuable sections of a handoff are the list of claims already checked with a reproducible probe (so the next pass does not re-check them) and the list of claims that were not (so it knows where its value is highest). Name the probe, and record any measurement recipe that lived only in a session scratchpad.

## The plan index (`docs/execplans-status.md`)

**The index lives in [`execplans-status.md`](./execplans-status.md), not in `CLAUDE.md`.** It was moved out on 2026-09-14 for the reason this section already gave: status changes every session and `CLAUDE.md` is read every session, so the two have different lifetimes and do not belong in one file. `CLAUDE.md` now describes what an ExecPlan *is* and links onward; **do not add milestone state, dates, counts or next actions to it.**

The index lists the in-flight plans so an agent starting cold knows what exists and which file to open. It is an index, not a status report, and the distinction is load-bearing: a plan's state changes every session, and every copy of that state outside the plan is a copy that will be wrong within the week.

* **A plan row is a pointer, not a summary.** Name, one line on what it covers, current status, next action, and at most one gating constraint the reader must know before opening anything. Two or three sentences. If a row is growing past that, the material belongs in the plan.
* **The plan is the definitive record of its own state.** Milestone progress, test counts, per-finding review series, schema shapes, decision counts and open questions live in the plan's `Progress`, `Decision Log`, `Surprises & Discoveries` and `Outcomes & Retrospective` — where an agent that opens the plan will read them anyway, and where they cannot drift from it. Say so explicitly in the row rather than restating any of it.
* **Re-read the surrounding prose when you edit a row.** Section headers and framing sentences are written once and then quietly outlived by the bullets beneath them. A block introduced as "declared rather than designed" whose first entry now reads "design fully settled" has two authors and no editor.
* **Never state that a file does not exist.** A working tree is one branch's view. Concurrent sessions and worktrees routinely hold files yours cannot see, so "verified: no file on disk" is a claim about your checkout that reads as a claim about the repository — and dating it and marking it verified makes the next reader more likely to believe it. If a plan file is genuinely missing, say the bullet is currently the whole declaration and leave it at that.
* **Prefer removing a line to updating it.** If the plan says it better, delete the copy here.

# Prototyping milestones and parallel implementations

It is acceptable—-and often encouraged—-to include explicit prototyping milestones when they de-risk a larger change. Examples: adding a low-level operator to a dependency to validate feasibility, or exploring two composition orders while measuring optimizer effects. Keep prototypes additive and testable. Clearly label the scope as “prototyping”; describe how to run and observe results; and state the criteria for promoting or discarding the prototype.

Prefer additive code changes followed by subtractions that keep tests passing. Parallel implementations (e.g., keeping an adapter alongside an older path during migration) are fine when they reduce risk or enable tests to continue passing during a large migration. Describe how to validate both paths and how to retire one safely with tests. When working with multiple new libraries or feature areas, consider creating spikes that evaluate the feasibility of these features _independently_ of one another, proving that the external library performs as expected and implements the features we need in isolation.

## Skeleton of a Good ExecPlan

    # <Short, action-oriented description>

    This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

    If PLANS.md file is checked into the repo, reference the path to that file here from the repository root and note that this document must be maintained in accordance with PLANS.md.

    ## Purpose / Big Picture

    Explain in a few sentences what someone gains after this change and how they can see it working. State the user-visible behavior you will enable.

    ## Progress

    Use a list with checkboxes to summarize granular steps. Every stopping point must be documented here, even if it requires splitting a partially completed task into two (“done” vs. “remaining”). This section must always reflect the actual current state of the work.

    - [x] (2025-10-01 13:00Z) Example completed step.
    - [ ] Example incomplete step.
    - [ ] Example partially completed step (completed: X; remaining: Y).

    Use timestamps to measure rates of progress.

    ## Surprises & Discoveries

    Document unexpected behaviors, bugs, optimizations, or insights discovered during implementation. Provide concise evidence.

    - Observation: …
      Evidence: …

    ## Decision Log

    Record every decision made while working on the plan in the format:

    - Decision: …
      Rationale: …
      Date/Author: …

    ## Outcomes & Retrospective

    Summarize outcomes, gaps, and lessons learned at major milestones or at completion. Compare the result against the original purpose.

    ## Context and Orientation

    Describe the current state relevant to this task as if the reader knows nothing. Name the key files and modules by full path. Define any non-obvious term you will use. Do not refer to prior plans.

    ## Plan of Work

    Describe, in prose, the sequence of edits and additions. For each edit, name the file and location (function, module) and what to insert or change. Keep it concrete and minimal.

    ## Concrete Steps

    State the exact commands to run and where to run them (working directory). When a command generates output, show a short expected transcript so the reader can compare. This section must be updated as work proceeds.

    ## Validation and Acceptance

    Describe how to start or exercise the system and what to observe. Phrase acceptance as behavior, with specific inputs and outputs. If tests are involved, say "run <project’s test command> and expect <N> passed; the new test <name> fails before the change and passes after>".

    ## Idempotence and Recovery

    If steps can be repeated safely, say so. If a step is risky, provide a safe retry or rollback path. Keep the environment clean after completion.

    ## Artifacts and Notes

    Include the most important transcripts, diffs, or snippets as indented examples. Keep them concise and focused on what proves success.

    ## Interfaces and Dependencies

    Be prescriptive. Name the libraries, modules, and services to use and why. Specify the types, traits/interfaces, and function signatures that must exist at the end of the milestone. Prefer stable names and paths such as `crate::module::function` or `package.submodule.Interface`. E.g.:

    In crates/foo/planner.rs, define:

        pub trait Planner {
            fn plan(&self, observed: &Observed) -> Vec<Action>;
        }

If you follow the guidance above, a single, stateless agent -- or a human novice -- can read your ExecPlan from top to bottom and produce a working, observable result. That is the bar: SELF-CONTAINED, SELF-SUFFICIENT, NOVICE-GUIDING, OUTCOME-FOCUSED.

When you revise a plan, you must ensure your changes are comprehensively reflected across all sections, including the living document sections, and you must write a note at the bottom of the plan describing the change and the reason why. ExecPlans must describe not just the what but the why for almost everything.