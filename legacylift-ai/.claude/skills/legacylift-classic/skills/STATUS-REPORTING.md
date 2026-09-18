# Status Reporting Standard

## Overview

All skills must report execution status to enable real-time progress tracking in the UI. When a skill runs via the claudeapi, it receives environment variables that specify where to write status updates.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SKILL_JOB_ID` | Unique job UUID for this execution |
| `SKILL_STATUS_FILE` | Full path to write status updates (e.g., `/home/node/skill-status/{job_id}.json`) |

## Status File Format

Write status updates as JSON to `$SKILL_STATUS_FILE`:

```json
{
  "phase": "Phase 3 of 7: Data Model Extraction",
  "phase_number": 3,
  "total_phases": 7,
  "progress_percent": 42,
  "current_task": "Analyzing entity relationships",
  "last_updated": "2026-02-12T10:30:00Z"
}
```

### Field Definitions

| Field | Type | Description |
|-------|------|-------------|
| `phase` | string | Human-readable phase description (e.g., "Phase 3 of 7: Data Model Extraction") |
| `phase_number` | integer | Current phase number (0-indexed) |
| `total_phases` | integer | Total number of phases in this skill |
| `progress_percent` | integer | Estimated progress percentage (0-100) |
| `current_task` | string | Brief description of current activity |
| `last_updated` | string | ISO 8601 timestamp (UTC) |

## Progress Calculation

Calculate progress percentage based on phase completion:

```
progress_percent = (phase_number / total_phases) * 100
```

Each skill should adjust the percentage within phases if appropriate.

## Implementation

At the **START** of each phase, update the status file using Bash:

```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"

# Example: Phase 3 of 7
echo '{"phase": "Phase 3 of 7: Data Model Extraction", "phase_number": 3, "total_phases": 7, "progress_percent": 42, "current_task": "Extracting data entities", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```

### Important Notes

1. **Fallback path**: If `$SKILL_STATUS_FILE` is not set, use `/home/node/skill-status/current.json`
2. **Overwrite**: Each status update overwrites the previous (use `>` not `>>`)
3. **Timing**: Update at phase transitions, not continuously
4. **Cleanup**: The claudeapi automatically deletes the status file when the job completes

## Skill-Specific Phases

Each skill defines its own phases in its SKILL.md. Common patterns:

| Skill Category | Typical Total Phases | Notes |
|----------------|---------------------|-------|
| Documentation generators | 8 (0-7) | Includes fact-graph loading, analysis, generation, review |
| Validators | 5-6 (0-4/5) | Parse, validate, report, optional auto-fix |
| Analyzers | 7 (0-6) | Discovery, extraction, analysis, detection, report, output |

## Integration with claudeapi

The claudeapi backend:

1. Creates the status directory (`/home/node/skill-status/`)
2. Passes `SKILL_JOB_ID` and `SKILL_STATUS_FILE` as environment variables
3. Reads the status file on `/job-status/{job_id}` API calls
4. Merges status data into the job response
5. Cleans up status files when jobs complete (success or failure)

## Example: 8-Phase Documentation Skill

```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"

# Phase 0 - Load Fact Graph
echo '{"phase": "Phase 0 of 7: Load Fact Graph", "phase_number": 0, "total_phases": 7, "progress_percent": 0, "current_task": "Checking for fact graph", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"

# Phase 1 - Initial Discovery
echo '{"phase": "Phase 1 of 7: Initial Discovery", "phase_number": 1, "total_phases": 7, "progress_percent": 14, "current_task": "Scanning repository structure", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"

# Phase 2 - Architecture Analysis
echo '{"phase": "Phase 2 of 7: Architecture Analysis", "phase_number": 2, "total_phases": 7, "progress_percent": 28, "current_task": "Analyzing architectural patterns", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"

# Phase 3 - Data Model Extraction
echo '{"phase": "Phase 3 of 7: Data Model Extraction", "phase_number": 3, "total_phases": 7, "progress_percent": 42, "current_task": "Extracting data entities", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"

# Phase 4 - Business Logic Analysis
echo '{"phase": "Phase 4 of 7: Business Logic Analysis", "phase_number": 4, "total_phases": 7, "progress_percent": 57, "current_task": "Analyzing business rules", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"

# Phase 5 - API & Integration Mapping
echo '{"phase": "Phase 5 of 7: API & Integration Mapping", "phase_number": 5, "total_phases": 7, "progress_percent": 71, "current_task": "Mapping API endpoints", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"

# Phase 6 - Document Generation
echo '{"phase": "Phase 6 of 7: Document Generation", "phase_number": 6, "total_phases": 7, "progress_percent": 85, "current_task": "Generating documentation with citations", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"

# Phase 7 - Review & Polish
echo '{"phase": "Phase 7 of 7: Review & Polish", "phase_number": 7, "total_phases": 7, "progress_percent": 95, "current_task": "Reviewing and validating", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```

## Example: 5-Phase Validator Skill

```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"

# Phase 0 - Load Fact Graph
echo '{"phase": "Phase 0 of 4: Load Fact Graph", "phase_number": 0, "total_phases": 4, "progress_percent": 0, "current_task": "Loading fact graph", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"

# Phase 1 - Parse Documentation
echo '{"phase": "Phase 1 of 4: Parse Documentation", "phase_number": 1, "total_phases": 4, "progress_percent": 25, "current_task": "Parsing documentation files", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"

# Phase 2 - Validate
echo '{"phase": "Phase 2 of 4: Validate", "phase_number": 2, "total_phases": 4, "progress_percent": 50, "current_task": "Validating content", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"

# Phase 3 - Generate Report
echo '{"phase": "Phase 3 of 4: Generate Report", "phase_number": 3, "total_phases": 4, "progress_percent": 75, "current_task": "Generating validation report", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"

# Phase 4 - Auto-Correct (optional)
echo '{"phase": "Phase 4 of 4: Auto-Correct", "phase_number": 4, "total_phases": 4, "progress_percent": 95, "current_task": "Auto-correcting issues", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```

---

*This is a shared reference document for the LegacyLift skills ecosystem.*
