# Integrate cloc into fact-graph for LOC Counting

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This document must be maintained in accordance with `docs/legacylift/exec-plan.md` (the ExecPlan authoring guide checked into this repository).


## Purpose / Big Picture

After this change, the `fact-graph` skill measures repository size using the `cloc` tool instead of a hand-rolled battery of nine `find` + `wc -l` shell batches. The user gains richer LOC data in the generated `index.json`: each language entry now includes separate counts for blank lines, comment lines, and source code lines (not just a single physical-line total). The `cloc` tool also honors `.gitignore` automatically via `--vcs=git`, which the old approach did not do, so git-ignored files are excluded without a manually maintained exclusion list.

A user can see the change working by running `fact-graph` on any test repository (for example `repos/ctcm-api`) and inspecting `legacylift-docs/context/index.json`. Before this change, `statistics.lines_of_code` contains a `by_extension` key mapping file extensions like `.cs` to raw line counts. After this change, it contains a `by_language` key mapping language names like `C#` to an object with `files`, `blank`, `comment`, `code`, `total`, and `percentage` fields, and the `methodology` note reflects that `cloc` was used.


## Progress

- [x] Milestone 1: Replace Phase 1.5 in `.claude/skills/fact-graph/SKILL.md` with a single `npx cloc` invocation and update the `loc_metrics` intermediate structure
- [x] Milestone 2: Update Phase 6 `generate_index` in the same file to map cloc's `by_language` output into `index.json`
- [x] Milestone 3: Update `.claude/skills/exec-summary-generator/SKILL.md` to read `by_language` instead of `by_extension`
- [x] Milestone 4: Update `.claude/skills/fact-graph/templates/index.schema.json` to reflect the new `by_language` structure
- [x] Milestone 5: Update `.claude/skills/fact-graph/templates/README.md` example code to use `by_language`
- [ ] Milestone 6: End-to-end validation against `repos/ctcm-api`


## Surprises & Discoveries

None yet.


## Decision Log

- Decision: Replace `by_extension` with `by_language` in `index.json` rather than attempting to map cloc language names back to file extensions.
  Rationale: `cloc` groups by language (e.g., `"C#"`, `"JavaScript"`) not by file extension. Mapping language names back to canonical extensions would require a lookup table that is difficult to keep correct across cloc versions and edge cases (a single language can map to many extensions, and some extensions are ambiguous). Using `by_language` directly is simpler, more accurate, and more informative to consumers.
  Date/Author: 2026-03-10 / dnorton

- Decision: Set `total_loc` to `SUM.blank + SUM.comment + SUM.code` (the physical line total) rather than `SUM.code` alone.
  Rationale: The existing `total_loc` field in `index.json` is documented as "total lines of code across all analyzed files" and consumers like `exec-summary-generator` display it as a repository size metric. Switching it to code-only lines would silently change the number shown to users, which could be confusing when comparing runs before and after the upgrade. Keeping `total_loc` as the physical total preserves the meaning while the richer per-language breakdown (blank, comment, code) allows consumers to extract code-only counts if desired.
  Date/Author: 2026-03-10 / dnorton

- Decision: Remove the nine-batch `find`+`wc -l` TodoWrite checkpoint pattern rather than keeping it as a fallback.
  Rationale: The checkpoints existed to survive context refresh during a slow multi-batch operation. A single `npx cloc` command completes in one tool call, so there is nothing to checkpoint. Keeping the old batches as a fallback would double the complexity of Phase 1.5 for no benefit because `cloc` is available on any machine that has Node.js (the same prerequisite the `cloc` skill already checks).
  Date/Author: 2026-03-10 / dnorton

- Decision: Use `--vcs=git` when the target is a git repository, falling back to `--not-match-d=legacylift` without `--vcs=git` when it is not.
  Rationale: This mirrors the exact logic in `.claude/skills/cloc/SKILL.md` and ensures fact-graph counts the same files that a standalone `/cloc` run would count.
  Date/Author: 2026-03-10 / dnorton

- Decision: The cloc report (`cloc-report.json`) is saved to `legacylift-docs/context/`, the same directory where fact-graph writes `index.json` and all pack files.
  Rationale: All LegacyLift machine-readable artifacts for a repository are stored under `legacylift-docs/context/`. Placing the cloc report there makes it immediately discoverable by any skill that already loads the fact graph. It also enables fact-graph's Phase 1.5 to check for a pre-existing `legacylift-docs/context/cloc-report.json` and use it instead of re-running cloc, which avoids a redundant network download on the first run. The check is simple: if the file exists and is valid JSON with a `by_language` key, use it; otherwise run cloc and write the result.
  Date/Author: 2026-03-10 / dnorton


## Outcomes & Retrospective

Not yet complete.


## Context and Orientation

LegacyLift's `fact-graph` skill lives at `.claude/skills/fact-graph/SKILL.md`. It is a large instruction document (roughly 2 600 lines) that Claude follows step by step. The skill is organized into six numbered phases. Phase 1 is "Repository Discovery" and contains sub-phases 1.1 through 1.6. Sub-phase 1.5, "Count Lines of Code", is the section this plan replaces.

**What Phase 1.5 does today** (lines ~294–659 in `SKILL.md`):
It executes nine batches of `find` + `wc -l` shell commands, each covering a different family of languages (JVM, .NET, JS/TS, SQL, Python, web frontend, config files, build scripts, other languages). Each batch produces per-extension numbers. After all nine batches run, the results are accumulated into an intermediate Python-style JSON structure called `loc_metrics`:

    {
      "total_loc": 0,
      "total_files": 0,
      "by_extension": {
        ".cs":   { "loc": 0, "files": 0 },
        ".java": { "loc": 0, "files": 0 }
      }
    }

This structure is passed to Phase 6 to populate `index.json`.

**Problems with the current approach:**
1. `find` walks the filesystem and does not honor `.gitignore`. The excluded-path patterns are a manually maintained list (`*/obj/*`, `*/bin/*`, etc.) that will inevitably fall out of date.
2. `wc -l` counts every physical line including blank lines and comments. The output is a single number per extension with no breakdown.
3. Nine batches means nine round trips, plus TodoWrite checkpoints between each.

**What the `cloc` skill offers** (already implemented at `.claude/skills/cloc/SKILL.md`): A single `npx cloc --vcs=git --not-match-d=legacylift --json <path>` command returns a JSON object whose keys are language names and whose values contain `nFiles`, `blank`, `comment`, and `code` counts. There is also a `"SUM"` key that aggregates across all languages. Because `--vcs=git` is used, the file list comes from `git ls-files`, which automatically applies `.gitignore`. The `--not-match-d=legacylift` flag excludes any directory whose name contains the string `legacylift` (for example `legacylift-docs`).

**Shared output directory**: Both the `cloc` skill (when `save=true`) and the `fact-graph` skill write into `legacylift-docs/context/` inside the analyzed repository. The `cloc` skill writes `cloc-report.json`; the `fact-graph` skill writes `index.json` and domain pack files under `packs/`. This co-location is intentional: fact-graph's Phase 1.5 can check for a pre-existing `cloc-report.json` and skip re-running cloc if a fresh one is already present from a prior `/cloc save=true` run.

**Files touched by this plan** (all paths relative to the repository root `legacylift-ai/`):

- `.claude/skills/fact-graph/SKILL.md` — the main file; two sections are edited: Phase 1.5 and Phase 6 `generate_index`
- `.claude/skills/exec-summary-generator/SKILL.md` — reads `by_extension` from the fact graph; update to `by_language`
- `.claude/skills/fact-graph/templates/index.schema.json` — JSON Schema that documents the shape of `index.json`; update `by_extension` → `by_language`
- `.claude/skills/fact-graph/templates/README.md` — usage examples that reference `by_extension`; update to `by_language`

**Downstream consumers of `lines_of_code` in `index.json`**: Only `exec-summary-generator` reads these fields in any skill. It reads `total_loc`, `total_files`, and `by_extension`. The `by_extension` variable is assigned but not referenced again in the snippet visible in that file, suggesting it is used implicitly in a narrative section. The plan updates both the assignment and any subsequent references.

**cloc JSON output format** (reference): when `npx cloc --vcs=git --not-match-d=legacylift --json .` is run on a .NET repository, the output looks like:

    {
      "header": {
        "cloc_url": "https://github.com/AlDanial/cloc",
        "n_files": 370,
        ...
      },
      "C#": {
        "nFiles": 342,
        "blank": 8421,
        "comment": 14032,
        "code": 62109
      },
      "JSON": {
        "nFiles": 28,
        "blank": 12,
        "comment": 0,
        "code": 3847
      },
      "SUM": {
        "nFiles": 370,
        "blank": 8433,
        "comment": 14032,
        "code": 65956
      }
    }

`SUM.nFiles` is the total file count; `SUM.blank + SUM.comment + SUM.code` is the total physical line count that will be stored as `total_loc`.


## Plan of Work

There are four files to edit. Edit them in the order listed; each is independent of the others and can be validated separately.

**Step 1: Replace Phase 1.5 in `.claude/skills/fact-graph/SKILL.md`.**

Locate sub-phase 1.5 by searching for the heading `#### 1.5 Count Lines of Code`. The section runs from that heading to the line immediately before `### Phase 1.6: Domain Classification`. Delete everything between those two boundaries and replace it with the following content:

    #### 1.5 Count Lines of Code

    Generate LOC metrics for the codebase to be included in the fact graph index. This step runs a single `cloc` command via `npx` and parses its JSON output.

    **Objective:** Count lines of code by language, distinguishing blank lines, comment lines, and source code lines. Honor `.gitignore` rules so that git-ignored files are excluded automatically.

    **Step 1: Check for a pre-existing cloc report.**

    The `/cloc save=true` skill writes its output to `legacylift-docs/context/cloc-report.json` in the analyzed repository — the same directory where fact-graph stores `index.json` and pack files. If this file already exists from a prior run, use it directly and skip Steps 2 and 3:

        test -f <path>/legacylift-docs/context/cloc-report.json && cat <path>/legacylift-docs/context/cloc-report.json

    If the file exists and is valid JSON, read it as the `loc_metrics` input for Phase 6 (it already contains `total_loc`, `total_files`, and `by_language` in the format produced by Step 3 below). Skip to Phase 1.6.

    If the file does not exist, continue with Step 2.

    **Step 2: Determine whether the target path is a git repository.**

        git -C <path> rev-parse --is-inside-work-tree 2>/dev/null

    If the output is `true`, set `USE_GIT=true`. Otherwise set `USE_GIT=false`.

    **Step 3: Run cloc with JSON output.**

    When `USE_GIT=true`:

        npx cloc --vcs=git --not-match-d=legacylift --json <path>

    When `USE_GIT=false`:

        npx cloc --not-match-d=legacylift --json <path>

    If `npx` is not available (command not found or non-zero exit), fall back to storing an empty `loc_metrics` structure and proceed. Log a warning for the user.

    Capture the JSON output.

    **Step 4: Parse the cloc output into `loc_metrics`.**

    Write the captured output to `/tmp/cloc_raw.json`, then run:

        python3 -c "
        import json, sys
        data = json.load(open('/tmp/cloc_raw.json'))
        total_sum = data.get('SUM', {})
        total_loc = total_sum.get('blank', 0) + total_sum.get('comment', 0) + total_sum.get('code', 0)
        total_files = total_sum.get('nFiles', 0)
        by_language = {}
        for lang, val in data.items():
            if lang in ('header', 'SUM'):
                continue
            if not isinstance(val, dict):
                continue
            blank   = val.get('blank', 0)
            comment = val.get('comment', 0)
            code    = val.get('code', 0)
            total   = blank + comment + code
            by_language[lang] = {
                'files':   val.get('nFiles', 0),
                'blank':   blank,
                'comment': comment,
                'code':    code,
                'total':   total
            }
        result = {
            'total_loc':   total_loc,
            'total_files': total_files,
            'by_language': by_language
        }
        print(json.dumps(result))
        "

    Store the printed JSON as the `loc_metrics` value that is passed into Phase 6.

**Step 2: Update Phase 6 `generate_index` in `.claude/skills/fact-graph/SKILL.md`.**

Locate the `generate_index` function definition at roughly line 2332. Find the block that calculates `by_extension` percentages:

    # Calculate percentages for LOC by extension
    total_loc = loc_metrics.get("total_loc", 0)
    by_extension = {}
    for ext, metrics in loc_metrics.get("by_extension", {}).items():
        loc = metrics["loc"]
        files = metrics["files"]
        percentage = round((loc / total_loc * 100), 1) if total_loc > 0 else 0
        by_extension[ext] = {
            "loc": loc,
            "files": files,

Replace that block, and the corresponding `"by_extension": by_extension` line in the returned dict, with code that reads `by_language` and adds percentages:

    # Calculate percentages for LOC by language (cloc output)
    total_loc = loc_metrics.get("total_loc", 0)
    by_language = {}
    for lang, metrics in loc_metrics.get("by_language", {}).items():
        total_lines = metrics.get("total", 0)
        percentage = round((total_lines / total_loc * 100), 1) if total_loc > 0 else 0
        by_language[lang] = {
            "files":      metrics.get("files", 0),
            "blank":      metrics.get("blank", 0),
            "comment":    metrics.get("comment", 0),
            "code":       metrics.get("code", 0),
            "total":      total_lines,
            "percentage": percentage
        }

In the dict that is returned by `generate_index`, change:

    "lines_of_code": {
        "total_loc": loc_metrics.get("total_loc", 0),
        "total_files": loc_metrics.get("total_files", 0),
        "by_extension": by_extension,
        "excluded_patterns": [
            "*/obj/*", "*/bin/*", "*.g.cs", "*.AssemblyInfo.cs", "*.AssemblyAttributes.cs",
            "*/node_modules/*", "*/legacylift-docs/*", "*/build/*",
            "*/target/*", "*/dist/*", "*/__pycache__/*", "*/venv/*"
        ],
        "methodology": "Total line count using wc -l (includes comments and blank lines)"
    },

to:

    "lines_of_code": {
        "total_loc":   loc_metrics.get("total_loc", 0),
        "total_files": loc_metrics.get("total_files", 0),
        "by_language": by_language,
        "methodology": "cloc --vcs=git (total = blank + comment + code; git-tracked files only; legacylift* directories excluded)"
    },

Note that `excluded_patterns` is removed because the new approach uses `--vcs=git` and `--not-match-d=legacylift` at the cloc level rather than a manually maintained list in the JSON.

**Step 3: Update `.claude/skills/exec-summary-generator/SKILL.md`.**

Locate the line (around line 205):

    by_extension = loc_metrics.get('by_extension', {})

Change it to:

    by_language = loc_metrics.get('by_language', {})

Then search for any subsequent reference to `by_extension` in the same file and rename each to `by_language`.

**Step 4: Update `.claude/skills/fact-graph/templates/index.schema.json`.**

Find the `"by_extension"` property definition inside the `"lines_of_code"` object. Rename the key to `"by_language"`. Update its `description` field to `"LOC breakdown by language as reported by cloc"`. Update the per-entry property definitions to add `blank`, `comment`, `code`, and `total` integer properties alongside `files` and `percentage`. Remove the `loc` property (it is superseded by the four new fields). Remove the `excluded_patterns` array property from the `lines_of_code` object. Update the `methodology` description to reference `cloc`.

**Step 5: Update `.claude/skills/fact-graph/templates/README.md`.**

Find the example code blocks that reference `by_extension` (near lines 385 and 457). Rename the variable and key to `by_language`. Update the field access from `stats['loc']` to `stats['code']` where code-line counts are displayed, and note that `stats['total']` is the physical line count (blank + comment + code). Update any example JSON snippets that show the `lines_of_code` object shape to use `by_language` and the new sub-fields.


## Concrete Steps

All commands are run from the repository root (`legacylift-ai/`).

**1. Edit Phase 1.5 in fact-graph.**

    # Open the file and locate the heading
    grep -n "1.5 Count Lines of Code" .claude/skills/fact-graph/SKILL.md

Note the line numbers for the start of Phase 1.5 and the start of Phase 1.6 (`### Phase 1.6`). Read those lines, then replace everything between them with the new Phase 1.5 content specified in the Plan of Work above.

**2. Edit the `generate_index` function in fact-graph.**

    grep -n "by_extension\|excluded_patterns\|wc -l" .claude/skills/fact-graph/SKILL.md

Identify the two locations: the percentage-calculation block and the returned dict's `lines_of_code` section. Apply the replacements described in Step 2 of the Plan of Work.

**3. Edit exec-summary-generator.**

    grep -n "by_extension" .claude/skills/exec-summary-generator/SKILL.md

Apply the rename described in Step 3 of the Plan of Work.

**4. Edit index.schema.json.**

    cat .claude/skills/fact-graph/templates/index.schema.json | grep -n "by_extension\|excluded_patterns\|methodology"

Apply the schema changes described in Step 4 of the Plan of Work.

**5. Edit templates/README.md.**

    grep -n "by_extension\|stats\['loc'\]" .claude/skills/fact-graph/templates/README.md

Apply the renames described in Step 5 of the Plan of Work.

**6. End-to-end validation.**

From a shell, navigate into the ctcm-api test repository and run fact-graph:

    cd repos/ctcm-api
    claude --skill fact-graph .

After the skill completes, inspect the index file:

    python3 -c "
    import json
    idx = json.load(open('legacylift-docs/context/index.json'))
    loc = idx['statistics']['lines_of_code']
    print('total_loc:',   loc['total_loc'])
    print('total_files:', loc['total_files'])
    print('methodology:', loc['methodology'])
    print('languages:')
    for lang, stats in loc.get('by_language', {}).items():
        print(f'  {lang}: files={stats[\"files\"]} blank={stats[\"blank\"]} comment={stats[\"comment\"]} code={stats[\"code\"]} total={stats[\"total\"]} pct={stats[\"percentage\"]}%')
    "

Expected: `by_language` is present; each language entry has `files`, `blank`, `comment`, `code`, `total`, and `percentage`; the `methodology` string mentions `cloc`; `by_extension` is absent; `excluded_patterns` is absent.

Also confirm `by_extension` no longer appears:

    python3 -c "
    import json
    idx = json.load(open('legacylift-docs/context/index.json'))
    loc = idx['statistics']['lines_of_code']
    assert 'by_extension' not in loc, 'by_extension still present'
    assert 'by_language' in loc, 'by_language missing'
    print('PASS')
    "


## Validation and Acceptance

The implementation is accepted when all of the following hold:

1. `index.json` contains `statistics.lines_of_code.by_language` (not `by_extension`).
2. Each entry in `by_language` has integer fields `files`, `blank`, `comment`, `code`, and `total`, and a float `percentage`.
3. `total` for each language equals `blank + comment + code`.
4. The sum of all `by_language[lang].total` values equals `total_loc` (within rounding).
5. `total_files` equals `by_language[lang].files` summed across all languages.
6. `statistics.lines_of_code` does not contain `by_extension` or `excluded_patterns`.
7. `methodology` contains the word `cloc`.
8. The `exec-summary-generator` skill does not reference `by_extension` anywhere.
9. `fact-graph/templates/index.schema.json` defines `by_language` and does not define `by_extension`.
10. `fact-graph/templates/README.md` references `by_language` and does not reference `by_extension`.


## Idempotence and Recovery

All steps are safe to repeat. Editing SKILL.md files is additive and deterministic; re-running the plan simply overwrites prior edits with the same content. Running fact-graph multiple times on the same repository overwrites `index.json` with fresh results.

If `npx cloc` fails (Node.js not installed, network unavailable), Phase 1.5 falls back to an empty `loc_metrics` structure (`total_loc: 0, total_files: 0, by_language: {}`). The `generate_index` function handles zero gracefully: percentages evaluate to `0.0` and the `by_language` object is empty. All other phases of fact-graph are unaffected.

If `python3` is not available, the parsing step (Step 3 of Phase 1.5) will fail. In that case, store the raw cloc JSON directly and perform the mapping inline during Phase 6 instead. This fallback should be noted but need not be pre-coded; `python3` is available on all platforms where LegacyLift is supported.


## Artifacts and Notes

The expected shape of `statistics.lines_of_code` in `legacylift-docs/context/index.json` after this change (abbreviated to three languages):

    "lines_of_code": {
      "total_loc": 88421,
      "total_files": 370,
      "by_language": {
        "C#": {
          "files": 342,
          "blank": 8421,
          "comment": 14032,
          "code": 62109,
          "total": 84562,
          "percentage": 95.6
        },
        "JSON": {
          "files": 28,
          "blank": 12,
          "comment": 0,
          "code": 3847,
          "total": 3859,
          "percentage": 4.4
        }
      },
      "methodology": "cloc --vcs=git (total = blank + comment + code; git-tracked files only; legacylift* directories excluded)"
    }

The `index.schema.json` `by_language` entry shape after this change:

    "by_language": {
      "type": "object",
      "description": "LOC breakdown by language as reported by cloc",
      "additionalProperties": {
        "type": "object",
        "properties": {
          "files":      { "type": "integer", "description": "Number of files in this language" },
          "blank":      { "type": "integer", "description": "Blank lines" },
          "comment":    { "type": "integer", "description": "Comment lines" },
          "code":       { "type": "integer", "description": "Source code lines" },
          "total":      { "type": "integer", "description": "Total physical lines (blank + comment + code)" },
          "percentage": { "type": "number",  "description": "Percentage of total_loc" }
        }
      }
    }


## Interfaces and Dependencies

The `fact-graph` skill depends on the Bash tool (already listed in its `allowed-tools` frontmatter). The new Phase 1.5 adds a runtime dependency on `npx` (ships with Node.js >= 5.2) and on the npm `cloc` package (downloaded on demand by `npx`). These are the same dependencies already declared in `.claude/skills/cloc/SKILL.md`. No changes to the `allowed-tools` frontmatter are needed.

The shape contract between Phase 1.5 and Phase 6 is the `loc_metrics` intermediate structure. After this change its definition is:

    loc_metrics = {
        "total_loc":   int,   # SUM.blank + SUM.comment + SUM.code
        "total_files": int,   # SUM.nFiles
        "by_language": {
            "<LanguageName>": {
                "files":   int,
                "blank":   int,
                "comment": int,
                "code":    int,
                "total":   int   # blank + comment + code
            },
            ...
        }
    }

The shape contract between `index.json` and downstream skills is the `statistics.lines_of_code` object. After this change it no longer contains `by_extension` or `excluded_patterns`. Any skill that read `by_extension` must be updated before using a fact graph generated after this change. The only known consumer is `exec-summary-generator`, which is updated in Milestone 3.
