# Add cloc Skill: Count Lines of Code in a Repository

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This document must be maintained in accordance with `docs/legacylift/exec-plan.md` (the ExecPlan authoring guide checked into this repository).


## Purpose / Big Picture

After this change, a LegacyLift user can invoke the `/cloc` skill from within Claude Code while navigating a legacy repository. The skill runs the `cloc` ("Count Lines of Code") tool against the repository, honoring its `.gitignore` rules so that vendor code, build artifacts, and other ignored files are excluded from the count. Results are shown in either a human-readable text table (the default) or a machine-readable JSON structure. The user can also choose to save the output to `legacylift-docs/` alongside other generated documentation.

Before this change, there is no automated way for LegacyLift skills to measure repository size. After this change, a user can run `/cloc` from any repository checkout and immediately see a language-by-language breakdown of source lines, comments, and blank lines — plus a computed "Total" column (blank + comment + code) for each language row — and can optionally persist that data as part of the documentation portfolio.


## Progress

- [x] (2026-03-09) Milestone 1: Create `.claude/skills/cloc/SKILL.md`
- [x] (2026-03-09) Milestone 2: Update `.claude/skills/README.md` skills inventory (row 18 added; count updated from 17 to 18)
- [ ] Milestone 3: Validate end-to-end against a test repository (requires running `/cloc` in a repo with Node.js available)


## Surprises & Discoveries

None yet.


## Decision Log

- Decision: Use the npm `cloc` package installed globally via `npm install -g cloc`, with `npx cloc` as the invocation command so no separate install step is required at skill runtime.
  Rationale: The user requested npm as the install mechanism. `npx` allows the skill to invoke `cloc` without requiring a prior global install; if the package is not cached, `npx` downloads and runs it automatically. If `npx` is unavailable, the fallback is `npm install -g cloc` followed by `cloc` directly.
  Date/Author: 2026-03-09 / dnorton

- Decision: Use `--vcs=git` to honor `.gitignore`.
  Rationale: `cloc --vcs=git <path>` internally runs `git ls-files <path>` to enumerate files, which causes git to apply all `.gitignore` rules (and `.git/info/exclude`) automatically. This is the most reliable way to exclude the same files that git ignores.
  Date/Author: 2026-03-09 / dnorton

- Decision: No template file is needed for this skill.
  Rationale: Unlike documentation generator skills that produce structured markdown documents with section headings and placeholders, the `cloc` skill either displays raw terminal output (text mode) or emits raw JSON. There is no layout to template. If saving to `legacylift-docs/context/`, the skill writes the raw cloc output directly.
  Date/Author: 2026-03-09 / dnorton

- Decision: This skill does not use Phase 0 (fact-graph loading).
  Rationale: The `cloc` skill does not analyze code structure, relationships, or semantics. It only counts lines. Loading the fact-graph would add latency without benefit.
  Date/Author: 2026-03-09 / dnorton

- Decision: Output files are named `legacylift-docs/context/cloc-report.txt` or `legacylift-docs/context/cloc-report.json` (not numbered with the 00-13 prefix scheme).
  Rationale: The existing 00-13 prefix scheme is reserved for documentation documents defined in the architecture reference (`docs/legacylift/architecture.md`). A cloc report is a utility artifact, not a documentation document, so it should not occupy a numbered slot. The `legacylift-docs/context/` sub-directory is where the fact-graph skill stores `index.json` and all pack files, making it the natural home for the cloc report as well. Co-locating them allows the fact-graph skill (or any other skill) to find a pre-existing cloc report without searching multiple directories.
  Date/Author: 2026-03-10 / dnorton

- Decision: The skill is categorized as "Utility" in the README skills inventory.
  Rationale: The skill does not fit into the existing Generator, Validator, Analyzer, or Exporter categories because it performs a purely mechanical measurement rather than analysis or documentation production.
  Date/Author: 2026-03-09 / dnorton

- Decision: Add `--not-match-d=legacylift` to all cloc invocations to exclude `legacylift*` directories.
  Rationale: LegacyLift writes its own generated output (JSON packs, markdown docs, reports) into `legacylift-docs/` inside the analyzed repository. Counting those files would inflate the language totals with LegacyLift's own artifacts rather than the repository's source code. The `--not-match-d` flag accepts a Perl regex, so `legacylift` matches any directory whose name contains that string (e.g., `legacylift-docs`, `legacylift-context`).
  Date/Author: 2026-03-10 / dnorton

- Decision: Add a "Total" column (blank + comment + code) to each language row, computed as a post-processing step rather than relying on cloc's native output.
  Rationale: `cloc` does not natively emit a total-lines column. The "Total" value (blank + comment + code) gives readers the full line count for a language at a glance without requiring them to add three numbers themselves. For text format, Phase 3 post-processes the raw cloc table using a short Python 3 script that appends the computed total to each data row and extends the separator lines. For JSON format, Phase 3 adds a `"total"` key to each language object before displaying or saving. Python 3 is used (rather than awk or sed) because it handles the variable-width cloc table format reliably and is available on all supported platforms.
  Date/Author: 2026-03-09 / dnorton


## Outcomes & Retrospective

Not yet complete.


## Context and Orientation

LegacyLift is a documentation platform whose core product is a set of Claude Code "skills". A skill is a directory under `.claude/skills/{skill-name}/` that contains at minimum a `SKILL.md` file. When a user invokes `/cloc` inside Claude Code (or runs `claude --skill cloc .` from the terminal), Claude reads that `SKILL.md` and follows its instructions to perform the task.

The `SKILL.md` file always starts with a YAML frontmatter block enclosed in `---` lines. The fields are:

    name: the-skill-name        # kebab-case; matches the directory name
    description: One-line summary shown in the skill picker
    allowed-tools: Bash         # comma-separated list of Claude Code tool names the skill may use

After the frontmatter comes plain English instructions that Claude will execute step by step.

The `.claude/skills/README.md` file maintains a human-readable inventory table of all skills. Every new skill must be added there.

The `cloc` tool is a command-line program that counts lines of code by programming language. It distinguishes source lines (actual code), comment lines, and blank lines. The npm package named `cloc` (https://www.npmjs.com/package/cloc) wraps the Perl `cloc` script in a cross-platform npm-installable form. The invocation `npx cloc` downloads and runs it on demand; no separate install step is required as long as Node.js and npm are present.

The `--vcs=git` command-line flag tells cloc to obtain its file list by running `git ls-files` on the target directory instead of walking the filesystem. This means only files that git tracks are counted, and all files matched by `.gitignore` rules are silently excluded.

The `--json` flag switches output from the human-readable text table to a JSON object. When `--json` is used, cloc emits an object whose keys are language names (e.g., `"C#"`, `"JSON"`) plus a special `"header"` key. Each language value contains `nFiles`, `blank`, `comment`, and `code` fields. The `cloc` skill adds a `"total"` field (`blank + comment + code`) to each language entry as a post-processing step, because cloc does not include this field natively.

For the text table format, cloc's native output has four numeric columns: `files`, `blank`, `comment`, and `code`. The skill appends a fifth column, `total`, to each language data row (computed as `blank + comment + code`) and extends the separator lines accordingly. This is done by saving the raw cloc output to a temp file and then running a short Python 3 script against it.

The `legacylift-docs/` directory at the root of an analyzed repository is where all LegacyLift skill outputs land. The `cloc` skill writes its output there only when the user passes the `save=true` parameter.

Key file paths relevant to this plan (all paths are relative to the repository root `legacylift-ai/`):

- `.claude/skills/cloc/SKILL.md` — the file to CREATE (does not exist yet)
- `.claude/skills/README.md` — the skills inventory to UPDATE


## Plan of Work

The work consists of two file changes: creating the skill definition and updating the skills inventory.

**Step 1: Create `.claude/skills/cloc/SKILL.md`.**

Create the directory `.claude/skills/cloc/` and write `SKILL.md` inside it. The file must begin with the YAML frontmatter block and then contain prose instructions for Claude to follow when the skill is invoked. No templates directory is needed.

The skill should accept three optional parameters parsed from the user's invocation text:

- `format` — `text` (default) or `json`. Controls whether cloc output is the human-readable table or a JSON object.
- `save` — `true` or `false` (default). When `true`, the skill writes the output to `legacylift-docs/context/cloc-report.txt` (for text) or `legacylift-docs/context/cloc-report.json` (for JSON) in addition to displaying it.
- `path` — An explicit path to the repository to analyze. Defaults to the current working directory (`.`).

The skill instructions should contain three phases:

Phase 1 (Verify Prerequisites) checks that `npx` is available by running `npx --version`. If `npx` is not found, the skill stops and instructs the user to install Node.js from https://nodejs.org. It also checks whether the current directory (or the provided `path`) is a git repository by running `git -C <path> rev-parse --is-inside-work-tree 2>/dev/null`. If it is not a git repository, the skill sets a fallback flag and will run cloc without `--vcs=git` in Phase 2.

Phase 2 (Run cloc) assembles and runs the cloc command. All invocations include `--not-match-d=legacylift` to exclude `legacylift*` output directories from the count. When the directory is a git repository, the command is:

    npx cloc --vcs=git --not-match-d=legacylift [--json] <path>

When not a git repository (fallback), the command omits `--vcs=git`:

    npx cloc --not-match-d=legacylift [--json] <path>

The `--json` flag is included only when `format=json`.

Phase 3 (Augment with Total, then display and optionally save results) post-processes the raw cloc output to add a "Total" column before presenting it to the user.

For `format=text`, save the raw cloc output to `/tmp/cloc_raw.txt`, then run this Python 3 script to append the Total column:

    python3 -c "
    import re, sys
    lines = open('/tmp/cloc_raw.txt').read().splitlines()
    out = []
    for line in lines:
        if re.match(r'^-+\s*$', line):
            out.append(line + '-' * 16)
        elif 'blank' in line and 'comment' in line and 'code' in line:
            out.append(line + '           total')
        else:
            m = re.search(r'(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$', line)
            if m:
                blank = int(m.group(2))
                comment = int(m.group(3))
                code = int(m.group(4))
                out.append(line + f'{blank + comment + code:>16}')
            else:
                out.append(line)
    print('\n'.join(out))
    "

The script works as follows: separator lines (all dashes) get sixteen extra dashes to extend the horizontal rule; the header line (which contains the words `blank`, `comment`, and `code`) gets the label `total` appended; every data row whose last four tokens are integers gets the sum of the last three (blank + comment + code) appended right-aligned in a 16-character field; all other lines (such as the cloc version line at the top) pass through unchanged.

For `format=json`, save the raw cloc output to `/tmp/cloc_raw.json`, then run this Python 3 script to inject the `total` field:

    python3 -c "
    import json
    data = json.load(open('/tmp/cloc_raw.json'))
    for key, val in data.items():
        if key != 'header' and isinstance(val, dict):
            val['total'] = val.get('blank', 0) + val.get('comment', 0) + val.get('code', 0)
    print(json.dumps(data, indent=2))
    "

Display the augmented output to the user. When `save=true`, create `legacylift-docs/` if absent and write the augmented output (not the raw cloc output) to the appropriate file. Confirm the save path to the user.

**Step 2: Update `.claude/skills/README.md`.**

In the "Skills Inventory" table (which currently has 17 rows numbered 1-17), add a new row for `cloc` at position 18:

    | 18 | `/cloc` | Utility | `legacylift-docs/context/cloc-report.txt` or `legacylift-docs/context/cloc-report.json` (when `save=true`; otherwise display only) |


## Concrete Steps

All commands below are run from the repository root (`legacylift-ai/`).

**1. Create the skill directory and file.**

Create the directory `.claude/skills/cloc/` and write `.claude/skills/cloc/SKILL.md` with the following content (exact content to write is given below under "Artifacts and Notes").

**2. Verify the file was created correctly.**

    cat .claude/skills/cloc/SKILL.md

Confirm the YAML frontmatter is present, the file begins with `---`, and three phases are described.

**3. Update `.claude/skills/README.md`.**

Open `.claude/skills/README.md`. Find the "Skills Inventory" section (the table that starts with `| # | Skill | Type | Output |`). The table currently ends at row 17. Append row 18 immediately after row 17:

    | 18 | `/cloc` | Utility | `legacylift-docs/context/cloc-report.txt` or `cloc-report.json` (when `save=true`; otherwise display only) |

Also update the introductory sentence "LegacyLift provides a suite of 17 skills" to read "a suite of 18 skills".

**4. Confirm the README update.**

    grep -n "cloc" .claude/skills/README.md

Expected output shows two matching lines: the skills-count sentence and the table row.

**5. Run the skill against a test repository to validate end-to-end behavior.**

Navigate into one of the test repositories, for example:

    cd repos/ctcm-api

Then invoke the skill from Claude Code:

    /cloc

Expected behavior: Claude runs Phase 1 (confirms npx is available and the directory is a git repo), Phase 2 (runs `npx cloc --vcs=git .`), and Phase 3 (post-processes and displays a table that looks like):

    -------------------------------------------------------------------------------------------------
    Language                     files          blank        comment           code            total
    -------------------------------------------------------------------------------------------------
    C#                             342           8421          14032          62109            84562
    JSON                            28             12              0           3847             3859
    ...
    -------------------------------------------------------------------------------------------------
    SUM:                           ...                                                         total

Then validate with `save=true`:

    /cloc save=true

Expected: same output plus a confirmation line such as "Saved to legacylift-docs/context/cloc-report.txt". Verify the file exists:

    ls repos/ctcm-api/legacylift-docs/context/cloc-report.txt

Then validate JSON format:

    /cloc format=json

Expected: Claude displays a JSON object whose top-level keys are language names (e.g., `"C#"`, `"JSON"`, `"SUM"`) each containing `nFiles`, `blank`, `comment`, `code`, and `total` fields. The `total` value for each language must equal `blank + comment + code`.


## Validation and Acceptance

The implementation is accepted when all of the following hold:

1. `.claude/skills/cloc/SKILL.md` exists, starts with valid YAML frontmatter, and contains three phases.
2. `.claude/skills/README.md` contains an entry for `/cloc` in its skills inventory.
3. Running `/cloc` in a git repository displays a language breakdown table excluding git-ignored files.
4. Running `/cloc format=json` displays a valid JSON object.
5. Running `/cloc save=true` writes `legacylift-docs/context/cloc-report.txt` in the analyzed repository.
6. Running `/cloc format=json save=true` writes `legacylift-docs/context/cloc-report.json`.
7. Running `/cloc` in a directory that is NOT a git repository still produces cloc output (fallback path, without `--vcs=git`).
8. The text table output includes a `total` column whose value for each language row equals that row's `blank + comment + code`.
9. The JSON output includes a `"total"` field on each language entry whose value equals `blank + comment + code` for that entry.


## Idempotence and Recovery

All steps are safe to repeat. Writing `SKILL.md` overwrites any prior version; the content is deterministic. The README update should be applied only once — if the row already exists, do not add it again. Running the skill multiple times simply overwrites the output file in `legacylift-docs/` with fresh results.

If `npx cloc` is slow on first run (because npm downloads the package), this is expected behavior. Subsequent runs will use the cached version and will be faster.


## Artifacts and Notes

The exact content for `.claude/skills/cloc/SKILL.md` is below. The agent implementing this plan should write this content verbatim to the file path.

    ---
    name: cloc
    description: Counts lines of code in a repository by language using cloc, honoring .gitignore rules. Outputs a text table or JSON. Optionally saves to legacylift-docs/.
    allowed-tools: Bash
    ---

    # cloc — Count Lines of Code

    This skill counts lines of code in the current repository (or a specified path) by programming language. It uses the `cloc` tool via `npx`, which requires no separate install step as long as Node.js is present. It honors `.gitignore` rules by leveraging git's own file listing when the target is a git repository.

    ## Parameters

    Parse the following optional parameters from the user's invocation:

    - `format` — `text` (default) or `json`. Controls cloc output format.
    - `save` — `true` or `false` (default `false`). When `true`, writes output to `legacylift-docs/` in the analyzed repository.
    - `path` — Path to the repository to analyze. Defaults to `.` (current directory).

    ## Examples

        /cloc
        /cloc format=json
        /cloc save=true
        /cloc format=json save=true
        /cloc path=repos/ctcm-api

    ## Execution Instructions

    Follow these phases in order. Do not skip a phase.

    ### Phase 1: Verify Prerequisites

    Check that npx is available:

        npx --version

    If the command fails (exit code non-zero or "command not found"), stop and tell the user:
    "npx is not available. Please install Node.js from https://nodejs.org and ensure npm is on your PATH, then retry."

    Determine whether the target path is inside a git repository:

        git -C <path> rev-parse --is-inside-work-tree 2>/dev/null

    If the output is `true`, the git mode is available. Set `USE_GIT=true`.
    If the command fails or returns anything other than `true`, set `USE_GIT=false` and note to the user that `.gitignore` rules will not be applied because the directory is not a git repository.

    ### Phase 2: Run cloc

    Assemble the cloc command based on the parameters:

    When `USE_GIT=true` and `format=text`:

        npx cloc --vcs=git --not-match-d=legacylift <path>

    When `USE_GIT=true` and `format=json`:

        npx cloc --vcs=git --not-match-d=legacylift --json <path>

    When `USE_GIT=false` and `format=text`:

        npx cloc --not-match-d=legacylift <path>

    When `USE_GIT=false` and `format=json`:

        npx cloc --not-match-d=legacylift --json <path>

    Run the command and capture its output.

    ### Phase 3: Augment with Total, Display, and Optionally Save

    Post-process the raw cloc output to add a "Total" column (blank + comment + code)
    before displaying or saving anything.

    For `format=text`, write the captured Phase 2 output to `/tmp/cloc_raw.txt`, then run:

        python3 -c "
        import re, sys
        lines = open('/tmp/cloc_raw.txt').read().splitlines()
        out = []
        for line in lines:
            if re.match(r'^-+\s*$', line):
                out.append(line + '-' * 16)
            elif 'blank' in line and 'comment' in line and 'code' in line:
                out.append(line + '           total')
            else:
                m = re.search(r'(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$', line)
                if m:
                    blank = int(m.group(2))
                    comment = int(m.group(3))
                    code = int(m.group(4))
                    out.append(line + f'{blank + comment + code:>16}')
                else:
                    out.append(line)
        print('\n'.join(out))
        "

    The script: extends separator lines (all-dash rows) by 16 extra dashes; appends
    the label `total` to the header row (identified by containing the words `blank`,
    `comment`, and `code`); appends the computed total right-aligned in a 16-character
    field to every data row whose last four tokens are integers; passes all other lines
    through unchanged.

    For `format=json`, write the captured Phase 2 output to `/tmp/cloc_raw.json`, then run:

        python3 -c "
        import json
        data = json.load(open('/tmp/cloc_raw.json'))
        for key, val in data.items():
            if key != 'header' and isinstance(val, dict):
                val['total'] = val.get('blank', 0) + val.get('comment', 0) + val.get('code', 0)
        print(json.dumps(data, indent=2))
        "

    Display the augmented output to the user.

    When `save=true`:

    1. Ensure the output directory exists:

           mkdir -p <path>/legacylift-docs/context

    2. Determine the output filename:
       - `format=text`: `<path>/legacylift-docs/context/cloc-report.txt`
       - `format=json`: `<path>/legacylift-docs/context/cloc-report.json`

    3. Write the augmented output (not the raw cloc output) to that file.

    4. Confirm to the user: "Saved to legacylift-docs/context/cloc-report.txt" (or .json).


## Interfaces and Dependencies

The skill depends only on the Bash tool (allowed in the frontmatter) and on two external executables being available in the shell environment:

- `npx` (ships with Node.js >= 5.2): used to invoke `cloc` without a global install
- `git` (any version): used to check if the target is a git repository and to enumerate tracked files via `--vcs=git`

The skill itself has no npm `package.json` and adds no dependencies to the `legacylift-ai` repository. It does not require the fact-graph, does not write markdown, and does not use any templates.
