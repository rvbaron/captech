# Running platform-ui from VS Code

**Why `platform-ui/.vscode/` did not work:** VS Code reads `launch.json` and
`tasks.json` only from the root of the folder you have open. You open
`legacylift-ai`, so a `.vscode/` folder nested inside `platform-ui/` was never
loaded. The configs now live in [`.vscode/`](../../.vscode/) at the repo root
(commit `ff2f2ed7`); reload the window and they appear.

## Without debugging — the simple path

**`Ctrl+Shift+B`** runs **`platform-ui: start both`**, the default build task:
`dotnet run` plus `ng serve`, in two dedicated terminals, nothing attached. Then
open <http://localhost:4200> yourself.

Or `Ctrl+Shift+P` → *Tasks: Run Task* for the individual ones:

| Task | Does |
|---|---|
| `platform-ui: start both` | API + web, no debugger |
| `platform-ui: run API` | just the API on :5189 |
| `platform-ui: serve Web` | just `ng serve` on :4200 |
| `platform-ui: prepare data` | rebuild `platform-ui/data` |
| `platform-ui: stop Web` | kill a stray `ng serve` |

## With debugging

`Ctrl+Shift+D`, pick **`platform-ui (API + Web)`**, F5. It builds the API,
attaches to it, starts `ng serve`, and launches Chrome at :4200 — C# and
TypeScript breakpoints both live. There is an Edge variant if you prefer it, and
the two halves can be launched separately.

**One caveat:** stop the debug session (or run `platform-ui: stop Web`) before
starting again. A leftover `ng serve` holds :4200, and a leftover API holds the
`.exe` so the next build fails with a file-lock error.

## Outside VS Code

```bash
cd platform-ui/api && dotnet run          # :5189
cd platform-ui/web && npm start           # :4200, proxies /api to :5189
```

`npm install` needs `--legacy-peer-deps` on this machine — see
[`platform-ui/README.md`](../../platform-ui/README.md).

## Two things that changed with the move

- `.gitignore`'s `.vscode` allowlist now includes `launch.json`, so the config is
  shared rather than per-machine.
- A latent bug the build had been warning about is fixed: in `graph.ts` the `|`
  pipe bound tighter than `??`, so `d.fileCounts[id] ?? 0 | number` parsed as
  `d.fileCounts[id] ?? (0 | number)` and a domain with no tagged files would have
  rendered blank. Every lookup now goes through one guarded `files()` method.
  Domain counts re-verified identical afterwards.

## Troubleshooting

### Failed to bind to address http://127.0.0.1:5189: address already in use.

If you get:
```
Exception has occurred: CLR/System.IO.IOException
  An unhandled exception of type 'System.IO.IOException' occurred in System.Private.CoreLib.dll: 'Failed to bind to address http://127.0.0.1:5189: address already in use.'
```
Run the following PowerShell command:
```
  Get-Process LegacyLift.PlatformApi -ErrorAction SilentlyContinue | Stop-Process -Force
```