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

    /legacylift-classic:cloc
    /legacylift-classic:cloc format=json
    /legacylift-classic:cloc save=true
    /legacylift-classic:cloc format=json save=true
    /legacylift-classic:cloc path=repos/ctcm/ctcm-api

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

    npx cloc --vcs=git --fullpath --not-match-d=legacylift <path>

When `USE_GIT=true` and `format=json`:

    npx cloc --vcs=git --fullpath --not-match-d=legacylift --json <path>

When `USE_GIT=false` and `format=text`:

    npx cloc --fullpath --not-match-d=legacylift <path>

When `USE_GIT=false` and `format=json`:

    npx cloc --fullpath --not-match-d=legacylift --json <path>

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
