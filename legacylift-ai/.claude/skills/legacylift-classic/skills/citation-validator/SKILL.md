---
name: citation-validator
description: Validates and corrects line number references in documentation files against the actual codebase.
allowed-tools: Read, Edit, Glob, Grep, TodoWrite
user-invocable: true
---

## Overview

This skill validates line number references (citations) in documentation files against the actual codebase. It detects when cited line numbers have drifted due to code changes and can auto-correct them.

**Output**: `09-CITATION-VALIDATION-REPORT.md`

**Complements**: `/legacylift-classic:documentation-review` (semantic accuracy) - this skill focuses on **syntactic accuracy** of line number citations.

## Usage

```
/legacylift-classic:citation-validator path=<docs_path> [auto_fix=true|false]
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `path` | No | `legacylift-docs/` | Path to documentation folder to validate |
| `auto_fix` | No | `false` | If `true`, automatically correct drifted citations |

### Examples

```bash
# Validate citations in default docs folder
/legacylift-classic:citation-validator

# Validate specific documentation folder
/legacylift-classic:citation-validator path=repos/behavior_change_savings/legacylift-docs

# Validate and auto-fix drifted citations
/legacylift-classic:citation-validator path=repos/behavior_change_savings/legacylift-docs auto_fix=true
```

---

## Execution Guidelines: Persistence and Autonomy

**Your context window will be automatically compacted as it approaches its limit, allowing you to continue working indefinitely from where you left off. Therefore, do not stop tasks early due to token budget concerns.**

**Critical Requirements:**
- As you approach your token budget limit, save your current progress and state to memory before the context window refreshes
- Always be as persistent and autonomous as possible
- Complete tasks fully, even if the end of your budget is approaching
- Never artificially stop any task early regardless of the context remaining
- If context compaction occurs, resume exactly where you left off using incremental writing patterns
- Use markers like `<!-- MORE CONTENT TO FOLLOW -->` to enable seamless continuation after context refresh

**Handling Context Compaction:**
1. Document current progress in todo list
2. Ensure continuation markers are present in documents
3. After refresh, read documents to determine last completed section
4. Continue with next section/phase
5. Maintain same format and quality standards throughout

---

## Citation Patterns Supported

The skill recognizes these citation formats:

| Pattern | Example | Description |
|---------|---------|-------------|
| Emoji link | `[📄](file.py:123)` | Standard documentation citation |
| Source link | `[source](file.sql:45-67)` | Source code reference |
| Numbered | `[1](file.py:10)` | Multiple source citations |
| Named | `[Code](file.ts:99)` | Named reference |
| Range | `[📄](file.py:10-25)` | Line range citation |

### Regex Patterns

```regex
# Primary patterns
\[📄\]\(([^:)]+):(\d+)(?:-(\d+))?\)
\[source\]\(([^:)]+):(\d+)(?:-(\d+))?\)
\[\d+\]\(([^:)]+):(\d+)(?:-(\d+))?\)
\[[^\]]+\]\(([^:)]+\.(?:py|sql|ipynb|ts|js|txt|md|json|yaml|yml|sh|scala|java)):(\d+)(?:-(\d+))?\)
```

---

## Analysis Workflow

Execute these 5 phases sequentially. Use the TodoWrite tool to track progress.

### Phase 0: Load Fact Graph (if available)

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Load Fact Graph", "phase_number": 0, "total_phases": 4, "progress_percent": 0, "current_task": "Loading fact graph", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

**Objective**: Check for and load pre-generated fact graph to accelerate entity citation validation.

**Canonical Reference**: See [FACT-GRAPH-INTEGRATION.md](../FACT-GRAPH-INTEGRATION.md) for the complete Phase 0 specification shared across all skills.

**⚠️ Domain-Scoped Packs**: The fact-graph skill generates domain-scoped pack files (e.g., `core.entities.pack.json`, `points.entities.pack.json`).

```python
import os
import json
from pathlib import Path

# Check if fact graph exists
fact_graph_path = 'legacylift-docs/context/index.json'
fact_graph_loaded = False
entities = []
index_metadata = {}
statistics = {}
packs_metadata = []

if os.path.exists(fact_graph_path):
    try:
        # Load index
        with open(fact_graph_path) as f:
            index = json.load(f)
            index_metadata = index.get('metadata', {})
            statistics = index.get('statistics', {})
            packs_metadata = statistics.get('packs_metadata', [])

        # Load all domain-scoped pack files
        packs_dir = Path('legacylift-docs/context/packs')

        if packs_dir.exists():
            # Load entities from all domain packs
            for pack_file in sorted(packs_dir.glob('*.entities.pack.json')):
                with open(pack_file) as f:
                    pack_data = json.load(f)
                    domain_entities = pack_data.get('entities', [])
                    entities.extend(domain_entities)
                    print(f"   Loaded {len(domain_entities)} entities from {pack_file.name}")

        fact_graph_loaded = True
        print(f"\n✅ Loaded fact graph: {len(entities)} entities")
        print(f"   Domains: {len(packs_metadata)}")
    except Exception as e:
        print(f"⚠️ Failed to load fact graph: {e}")
        print("   Falling back to direct file validation")
        fact_graph_loaded = False
else:
    print("ℹ️ No fact graph found, using direct file validation")

# Helper functions for entity lookup
def build_entity_location_index():
    """Build fast lookup index: {file_path: {line_range: entity}}"""
    location_index = {}

    for entity in entities:
        file_path = entity['file']
        line_range = entity.get('line_range', [0, 0])

        if file_path not in location_index:
            location_index[file_path] = []

        location_index[file_path].append({
            'name': entity['name'],
            'type': entity['type'],
            'line_start': line_range[0],
            'line_end': line_range[1],
            'content_hash': entity.get('attributes', {}).get('content_hash'),
            'entity': entity
        })

    # Sort by line_start for each file
    for file_path in location_index:
        location_index[file_path].sort(key=lambda x: x['line_start'])

    return location_index

if fact_graph_loaded:
    entity_location_index = build_entity_location_index()
    print(f"   Built location index for {len(entity_location_index)} files")
```

**Usage in Phase 2 (Validate Citations):**

When fact-graph is loaded, use it to quickly validate entity citations:

```python
if fact_graph_loaded:
    # Fast entity citation validation
    if citation.file in entity_location_index:
        # Check if citation line falls within any entity's line range
        for entity_info in entity_location_index[citation.file]:
            if entity_info['line_start'] <= citation.line <= entity_info['line_end']:
                # Entity citation - validate against entity info
                print(f"✅ Entity citation: {entity_info['name']} ({entity_info['type']})")

                # Use content_hash for drift detection (if available)
                if entity_info['content_hash']:
                    # Fast drift check without file read
                    # (would need to recalculate hash from file to compare)
                    pass

                # Entity citation is valid
                report_valid(citation, entity_info)
                continue

    # Non-entity citation or entity not found - fall back to file read
    # ... continue with normal validation ...
else:
    # Fallback to file reads for all citations
    # ... original validation logic ...
```

**Benefits:**
- ✅ Fast validation for entity citations (class, function, endpoint, etc.)
- ✅ Entity line ranges already extracted (no file read needed for bounds check)
- ✅ Content hash available for drift detection (if implemented)
- ✅ Reduces file reads by ~30-40% (for entity citations)
- ⚠️ Note: Non-entity citations (string literals, values, comments) still require file reads

---

### Phase 1: Parse Documentation

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Parse Documentation", "phase_number": 1, "total_phases": 4, "progress_percent": 25, "current_task": "Parsing documentation files", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

**Objective**: Find all markdown files and extract citation patterns.

#### 1.1 Locate Documentation Files

```
Use Glob to find:
- {path}/**/*.md
```

#### 1.2 Extract Citations

For each markdown file:

1. **Read the file** using the Read tool
2. **Apply regex patterns** to extract all citations:
   ```
   Pattern: \[([^\]]*)\]\(([^:)]+):(\d+)(?:-(\d+))?\)

   Captures:
   - Group 1: Link text (📄, source, number, etc.)
   - Group 2: File path
   - Group 3: Start line number
   - Group 4: End line number (optional, for ranges)
   ```
3. **Record each citation** with:
   - Source markdown file
   - Line number in markdown where citation appears
   - Cited file path
   - Cited line number(s)
   - Surrounding context (the sentence/paragraph)

#### 1.3 Phase 1 Output

```
Citations Found: N
- file1.md: X citations
- file2.md: Y citations
...
```

---

### Phase 2: Validate Citations

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Validate Citations", "phase_number": 2, "total_phases": 4, "progress_percent": 50, "current_task": "Validating line number references", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

**Objective**: Check each citation against the actual codebase.

#### 2.1 Validation Rules

For each citation:

1. **File Existence**: Check if the cited file exists
2. **Line Bounds**: Check if cited line number is within file bounds
3. **Content Relevance**: Check if content at cited line matches the documentation claim

#### 2.2 Validation Process

```python
# Pseudocode for validation
for citation in citations:
    file_path = resolve_path(citation.file, base_path)

    # Check 1: File exists
    if not file_exists(file_path):
        report_invalid(citation, "FILE_NOT_FOUND")
        continue

    # Check 2: Read file
    content = read_file(file_path)
    lines = content.split('\n')
    total_lines = len(lines)

    # Check 3: Line bounds
    if citation.line > total_lines:
        report_invalid(citation, "LINE_OUT_OF_BOUNDS",
                      f"File has {total_lines} lines, cited line {citation.line}")
        continue

    # Check 4: Content at line
    actual_content = lines[citation.line - 1]  # 1-indexed

    # Extract key identifiers from documentation context
    expected_patterns = extract_key_patterns(citation.context)

    # Check if any expected pattern is at cited line
    if any_pattern_at_line(expected_patterns, actual_content):
        report_valid(citation)
    else:
        # Search nearby lines for drift detection
        drift_result = search_nearby(lines, citation.line, expected_patterns, range=5)
        if drift_result.found:
            report_drift(citation, drift_result.line, drift_result.offset)
        else:
            report_invalid(citation, "CONTENT_MISMATCH",
                          f"Expected patterns not found at line {citation.line}")
```

#### 2.3 Key Pattern Extraction

To validate content relevance, extract key identifiers from the documentation context:

| Documentation Claim | Key Patterns to Search |
|---------------------|------------------------|
| "Delete code = 'Child_Parent_Child'" | `Child_Parent_Child`, `delete_code` |
| "REVERT with code 'TS'" | `'TS'`, `revert`, `TS` |
| "Validate ratio: 0.5" | `0.5`, `ratio`, `validate` |
| "dbutils.widgets.text" | `dbutils.widgets.text`, `widgets` |

#### 2.4 Status Categories

| Status | Description | Action |
|--------|-------------|--------|
| **VALID** | Line exists and content matches expected pattern | None |
| **DRIFT** | Content found within ±5 lines | Auto-correctable |
| **INVALID_FILE** | Referenced file does not exist | Manual fix required |
| **INVALID_LINE** | Line number exceeds file length | Manual fix required |
| **INVALID_CONTENT** | Content not found near cited line | Manual review required |

---

### Phase 3: Generate Report

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Generate Report", "phase_number": 3, "total_phases": 4, "progress_percent": 75, "current_task": "Generating validation report", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

**Objective**: Produce a summary of validation results.

#### 3.1 Report Format

Write the report to `{docs_path}/09-CITATION-VALIDATION-REPORT.md`:

```markdown
# Citation Validation Report

**Documentation Path**: {path}
**Date**: {timestamp}
**Auto-Fix Mode**: {enabled/disabled}

## Summary

| Status | Count | Percentage |
|--------|-------|------------|
| VALID | N | X% |
| DRIFT | N | X% |
| INVALID | N | X% |
| **Total** | **N** | **100%** |

## Valid Citations

All {N} valid citations verified successfully.

## Drifted Citations (Auto-Correctable)

| # | Doc File | Line | Cited Path | Old Line | New Line | Offset |
|---|----------|------|------------|----------|----------|--------|
| 1 | 03-BUS...md | 94 | file.py | 56 | 58 | +2 |
| 2 | 03-BUS...md | 132 | file.py | 92 | 94 | +2 |

## Invalid Citations (Manual Review Required)

| # | Doc File | Line | Cited Path | Issue | Details |
|---|----------|------|------------|-------|---------|
| 1 | doc.md | 45 | missing.py | FILE_NOT_FOUND | File does not exist |
| 2 | doc.md | 67 | file.py | LINE_OUT_OF_BOUNDS | File has 50 lines |

## Recommendations

1. **Drifted citations**: Run with `auto_fix=true` to automatically correct
2. **Invalid files**: Check if files were renamed or moved
3. **Invalid content**: Review documentation claims for accuracy
```

---

### Phase 4: Auto-Correct (Optional)

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Auto-Correct", "phase_number": 4, "total_phases": 4, "progress_percent": 95, "current_task": "Auto-correcting citations", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

**Objective**: Fix drifted citations if `auto_fix=true`.

#### 4.1 Correction Process

For each DRIFT citation:

1. **Locate the citation** in the markdown file
2. **Build replacement string**:
   ```
   Original: [📄](file.py:56)
   Corrected: [📄](file.py:58)
   ```
3. **Use Edit tool** to update the markdown file
4. **Verify the edit** was successful

#### 4.2 Correction Safety Rules

- Only correct DRIFT status (never INVALID)
- Preserve link text exactly (📄, source, [1], etc.)
- Preserve file path exactly
- Only update line numbers
- Log all corrections made

#### 4.3 Post-Correction Verification

After all corrections:

1. Re-read corrected files
2. Re-validate corrected citations
3. Report final status

---

## Skill Execution

When this skill is invoked, I will:

1. **Parse Parameters**
   - Extract `path` (default: `legacylift-docs/`)
   - Extract `auto_fix` (default: `false`)

2. **Create Todo List**
   - Phase 0: Load Fact Graph (if available)
   - Phase 1: Parse Documentation
   - Phase 2: Validate Citations
   - Phase 3: Generate Report
   - Phase 4: Auto-Correct (if enabled)

3. **Execute Validation**
   - Load fact graph if available (Phase 0) for fast entity citation validation
   - Use Glob to find all markdown files
   - Use Read to extract citations from each file
   - If fact-graph loaded: Use entity location index for entity citations
   - If fact-graph NOT loaded or non-entity citations: Use Read to validate each cited file and line
   - Build validation results

4. **Generate Report**
   - Summarize findings
   - List all issues with details
   - Provide recommendations

5. **Auto-Correct (if enabled)**
   - Use Edit to fix drifted citations
   - Report corrections made

6. **Provide Summary**
   - Total citations checked
   - Validation pass rate
   - Issues found and fixed

---

## Implementation Details

### Path Resolution

Citations may use relative or absolute paths. Resolution strategy:

```python
def resolve_citation_path(cited_path, markdown_file, docs_root):
    """
    Resolve a citation path to an absolute path.

    Try in order:
    1. Relative to the repository root (most common)
    2. Relative to the docs directory
    3. Relative to the markdown file's directory
    4. As absolute path
    """
    candidates = [
        repo_root / cited_path,
        docs_root / cited_path,
        markdown_file.parent / cited_path,
        Path(cited_path)
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None  # File not found
```

### URL-Encoded Paths

Some citations may have URL-encoded spaces (e.g., `TXT/Behavior%20Change%20Guidelines.txt`):

```python
from urllib.parse import unquote

def decode_path(cited_path):
    return unquote(cited_path)  # Converts %20 to spaces
```

### Drift Detection Algorithm

```python
def search_nearby(lines, cited_line, patterns, range=5):
    """
    Search for patterns in lines near the cited line.

    Returns the closest line containing any pattern.
    """
    # Search in expanding circles: 0, ±1, ±2, ... ±range
    for offset in range(0, range + 1):
        for direction in [0, 1, -1] if offset == 0 else [1, -1]:
            check_line = cited_line + (offset * direction)

            if 1 <= check_line <= len(lines):
                line_content = lines[check_line - 1]

                for pattern in patterns:
                    if pattern.lower() in line_content.lower():
                        return DriftResult(
                            found=True,
                            line=check_line,
                            offset=check_line - cited_line,
                            pattern=pattern
                        )

    return DriftResult(found=False)
```

---

## Error Handling

| Error | Handling |
|-------|----------|
| Documentation folder not found | Report error, suggest valid paths |
| No markdown files found | Report, check if path is correct |
| Permission denied reading file | Skip file, log warning |
| Malformed citation pattern | Log and skip, continue with others |
| Edit tool failure | Log error, do not mark as corrected |

---

## Success Criteria

Validation is complete when:

- All markdown files in path have been scanned
- All citations have been validated
- Report has been generated
- (If auto_fix=true) All drifted citations have been corrected
- Summary statistics are accurate

---

## Supporting Files & Templates

This skill generates a validation report but does not use a template file. The output format is standardized.

### LegacyLift Documentation Ecosystem

This skill is part of the comprehensive LegacyLift documentation suite. Here's the complete set of documents available:

| Prefix | Document | Generated By | Description |
|--------|----------|--------------|-------------|
| **Core Documentation Suite** ||||
| 00 | EXECUTIVE-SUMMARY | exec-summary-generator | High-level overview for all stakeholders |
| 01 | SYSTEM-ARCHITECTURE | si-documenter | Technical architecture deep dive |
| 02 | DATA-MODEL-AND-RELATIONSHIPS | data-documenter, database-layer-documenter | Data structures and relationships |
| 03 | BUSINESS-RULES-AND-REQUIREMENTS | business-documenter, detailed-req-documenter | Functional requirements and rules |
| 04 | INTEGRATION-AND-API-GUIDE | si-documenter | API documentation and integration patterns |
| 05 | QUICK-REFERENCE | si-documenter | Glossary and quick lookups |
| **Extended Documentation & Analysis** ||||
| 06 | TABLE-VALIDATION-* | table-validation | ORM mapping validation reports |
| 07 | DOCUMENTATION-ACCURACY-REPORT | documentation-review | Documentation accuracy validation |
| 08 | USE-CASES-{DOMAIN} | use-case-generator | Comprehensive use case documentation |
| 09 | **CITATION-VALIDATION-REPORT** ⭐ | **citation-validator** | Citation correctness validation |
| 10 | GAP-ANALYSIS-REPORT | gap-analyzer | Documentation-code gap analysis |

⭐ = Generated by this skill (creates 09-CITATION-VALIDATION-REPORT.md)

---

## Example Output

```
Citation Validation Complete!

Documentation Path: repos/behavior_change_savings/legacylift-docs
Files Scanned: 5
Total Citations: 127

Results:
- VALID: 115 (90.6%)
- DRIFT: 8 (6.3%)
- INVALID: 4 (3.1%)

Auto-Fix: DISABLED

Drifted Citations:
1. 03-BUSINESS-RULES-VALIDATION-EXCLUSIONS.md:94 → file.py:56 should be :58 (+2)
2. 03-BUSINESS-RULES-VALIDATION-EXCLUSIONS.md:132 → file.py:92 should be :94 (+2)
...

Invalid Citations:
1. 03-BUSINESS-RULES-VALIDATION-EXCLUSIONS.md:245 → missing.py:10 - FILE NOT FOUND
...

Run with auto_fix=true to correct drifted citations.
```
