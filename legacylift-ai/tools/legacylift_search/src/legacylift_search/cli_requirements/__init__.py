"""The `requirements` Typer sub-application -- fourteen commands.

Milestone 1, Step 8 of `docs/exec-plans/active/reqs-to-data-store.md`.

**This is the first `app.add_typer` in `cli.py`.** Every other command in
this tool is a flat `@app.command` registration, so there was no precedent to
copy for the sub-app wiring itself; everything *inside* a command follows the
existing ones -- path resolution, `--json` output, `rich` tables, and the
read-only existence check `_shared.open_knowledge_store` performs.

The commands are split across four modules by what they do, and the split is
recorded here so that four independently-written modules cannot disagree
about who owns a command:

| Module            | Commands                                                |
|-------------------|---------------------------------------------------------|
| `read_cmds.py`    | `list`, `show`, `search`, `stats`                       |
| `write_cmds.py`   | `set-state`, `set-field`                                |
| `run_cmds.py`     | `ingest`, `validate`, `set-run-coverage`, `retire-run`  |
| `repair_cmds.py`  | `reindex-vectors`, `rederive-subjects`, `export`, `import` |

Two notes on that grouping, because neither is arbitrary. `validate` is in
`run_cmds` rather than `read_cmds` even though it writes nothing: it is the
command whose **exit code** is the completeness signal (non-zero while an
`ERROR` finding stands), which is a run-level concern and puts it beside the
two `gr_run` commands that answer the same audit question. And `export` and
`import` are in `repair_cmds` beside the two repair commands because all four
share the resumable-repair shape the plan names -- each recomputes or
restores a durable value, processes only what is stale, reports what it
changed and what it skipped, and is safe to run twice.

The four modules are imported at the bottom of this file **for their
registration side effect** -- each decorates its commands onto
`requirements_app` at import time -- so the import must come after the app
exists, and it is not unused.
"""

from __future__ import annotations

import typer

requirements_app = typer.Typer(
    name="requirements",
    help=(
        "Query and review generated requirements (GRs) in knowledge.sqlite.\n"
        "\n"
        "Extraction merges into this store rather than replacing it, so human "
        "review accumulates instead of evaporating. `set-state` is the only "
        "way a requirement leaves `draft`, it requires a named reviewer, and "
        "it refuses `approved` while any ERROR-severity finding stands."
    ),
    no_args_is_help=True,
)

# Imported for the side effect of registering their commands on the app
# above. Placed at the bottom because each module imports `requirements_app`
# from this one, so the app has to exist first. `noqa: E402/F401` is the
# ordinary spelling of a deliberate side-effect import.
from . import read_cmds as read_cmds  # noqa: E402,F401
from . import repair_cmds as repair_cmds  # noqa: E402,F401
from . import run_cmds as run_cmds  # noqa: E402,F401
from . import write_cmds as write_cmds  # noqa: E402,F401

__all__ = ["requirements_app"]
