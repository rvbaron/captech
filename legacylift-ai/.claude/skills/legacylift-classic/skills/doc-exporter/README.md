# Doc Exporter

Exports LegacyLift markdown documentation to professionally styled Word (.docx) or PDF (.pdf) documents using Pandoc. Mermaid diagrams are rendered as PNG images, not left as code blocks.

## Prerequisites

### Required: Pandoc

```bash
brew install pandoc

# Verify
pandoc --version | head -1
```

### Required: Mermaid CLI (for diagram rendering)

```bash
npm install -g @mermaid-js/mermaid-cli

# Verify
mmdc --version
```

Without `mmdc`, mermaid diagram blocks will remain as raw code in the exported document.

### Required for PDF only: WeasyPrint + system libraries

```bash
# 1. Install Pango (provides GLib, Cairo, Pango native libraries)
brew install pango

# 2. Install WeasyPrint
pip install weasyprint

# Verify
weasyprint --version
```

**macOS note**: PDF export commands must be prefixed with `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` so WeasyPrint can locate the Homebrew-installed native libraries. The skill handles this automatically.

## Usage

### Export all docs to Word (default)

```
/legacylift-classic:doc-exporter path=repos/my_project
```

### Export a single file to Word

```
/legacylift-classic:doc-exporter path=repos/agnostic_modules file=00-EXECUTIVE-SUMMARY.md
```

### Export all docs to PDF

```
/legacylift-classic:doc-exporter format=pdf path=repos/my_project
```

### Export a single file to PDF

```
/legacylift-classic:doc-exporter format=pdf path=repos/agnostic_modules file=00-EXECUTIVE-SUMMARY.md
```

### Export all docs as one consolidated Word document

```
/legacylift-classic:doc-exporter mode=consolidated path=repos/my_project
```

### Export all docs as one consolidated PDF

```
/legacylift-classic:doc-exporter format=pdf mode=consolidated path=repos/my_project
```

## Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `format` | No | `word` | Output format: `word` (.docx) or `pdf` (.pdf) |
| `mode` | No | `individual` | `individual` (one output per .md file) or `consolidated` (single combined document) |
| `path` | No | Current directory | Path to the repository containing `legacylift-docs/` |
| `file` | No | All `.md` files | Specific `.md` filename to export (e.g., `00-EXECUTIVE-SUMMARY.md`) |

## Output Location

Output files are written to a `docx/` or `pdf/` subdirectory inside the docs folder. Original markdown files are never modified.

```
repos/my_project/legacylift-docs/
├── docx/                              <- Word output
│   ├── 00-EXECUTIVE-SUMMARY.docx
│   ├── 01-SYSTEM-ARCHITECTURE.docx
│   └── ...
├── pdf/                               <- PDF output
│   ├── 00-EXECUTIVE-SUMMARY.pdf
│   └── ...
├── 00-EXECUTIVE-SUMMARY.md            <- original source (untouched)
├── 01-SYSTEM-ARCHITECTURE.md
└── ...
```

## How It Works

1. **Discover** — Locates `legacylift-docs/` (or `docs/`) in the target repository
2. **Verify** — Checks that `pandoc`, `mmdc`, and (for PDF) `weasyprint` are installed
3. **Pre-process Mermaid** — Extracts ` ```mermaid ` blocks, renders each to PNG via `mmdc`, replaces the code block with an image reference. Source citations like `[📄](file:line)` are automatically stripped before rendering
4. **Convert** — Runs Pandoc with a YAML title page (CapTech branding) and the reference template
5. **Report** — Confirms output files exist and reports sizes, diagram stats

## Key Behaviors

- **No duplicate TOC** — Pandoc's `--toc` flag is NOT used. The markdown source files already contain their own `## Table of Contents` sections
- **Mermaid code cleaning** — The backend renderer strips markdown citation links and `[Source: ...]` references from mermaid code before rendering, producing clean diagrams
- **Graceful degradation** — If `mmdc` is not installed or a specific diagram fails to render, the original code block is kept unchanged
- **Reference template** — Uses `tools/templates/reference.docx` for Word styling when available; falls back to Pandoc defaults if missing

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Mermaid diagrams appear as code blocks | Install mermaid-cli: `npm install -g @mermaid-js/mermaid-cli` |
| `pandoc: command not found` | Install Pandoc: `brew install pandoc` |
| PDF export fails with `libgobject` error | Install Pango: `brew install pango` |
| PDF export fails with `weasyprint not found` | Install WeasyPrint: `pip install weasyprint` |
| Duplicate Table of Contents in output | Ensure `--toc` flag is NOT being passed to Pandoc |
| CSS warnings during PDF export | Safe to ignore — WeasyPrint warns about unsupported CSS properties but still produces correct output |
