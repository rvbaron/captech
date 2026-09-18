---
name: documentation-review
description: Reviews generated documentation for accuracy by comparing technical claims against the actual source code repository.
allowed-tools: Read, Glob, Grep, Task, Write, Bash, TodoWrite
user-invocable: true
---

## Overview

This skill reviews LegacyLift-generated documentation for semantic accuracy. It extracts verifiable claims from documentation (architecture patterns, technology choices, data models, APIs, business rules, integrations) and validates them against the actual codebase.

**Key Differentiation from Related Skills:**
- **gap-analyzer**: Finds what's missing (documented but not in code, or vice versa)
- **citation-validator**: Validates line number citations are correct
- **documentation-review** (this skill): Verifies that claims in documentation are **semantically accurate**

## Usage

```
/legacylift-classic:documentation-review docs_path=<path> code_path=<path> output_dir=<path>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `docs_path` | No | Auto-detect | Path to documentation folder (tries: `legacylift-docs/`, `TXT/`, `docs/`, `documentation/`) |
| `code_path` | No | Current working directory | Path to the code repository |
| `output_dir` | No | `{code_path}/legacylift-docs/` | Where to write the accuracy report |

### Examples

```bash
# Review with explicit paths
/legacylift-classic:documentation-review docs_path=repos/my_project/legacylift-docs code_path=repos/my_project

# Auto-detect docs folder
/legacylift-classic:documentation-review code_path=repos/my_project

# Use all defaults
/legacylift-classic:documentation-review
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

## Claim Categories

The skill verifies claims in these categories:

| Category | What to Verify | Examples |
|----------|----------------|----------|
| **Architecture** | Patterns, service boundaries, component relationships | "Uses MVC pattern", "Microservices architecture", "Event-driven design" |
| **Technology** | Languages, frameworks, versions, dependencies | "Built with Python 3.9", "Uses FastAPI", "PostgreSQL database" |
| **Data Model** | Entities, fields, types, relationships, constraints | "User has many Orders", "email field is unique", "status enum values" |
| **API** | Endpoints, methods, parameters, responses | "POST /api/users creates user", "Returns 404 if not found" |
| **Business Rules** | Validation logic, workflows, calculations | "Password must be 8+ chars", "Orders auto-cancel after 24h" |
| **Integration** | External services, auth methods, protocols | "Integrates with Stripe API", "Uses OAuth 2.0", "Sends webhooks to Slack" |

---

## Verification Status Types

| Status | Definition | Score Weight |
|--------|------------|--------------|
| **ACCURATE** | Claim fully supported by code evidence | 1.0 |
| **PARTIAL** | Claim partially correct (some aspects verified, others not) | 0.5 |
| **INACCURATE** | Claim contradicts what is found in code | 0.0 |
| **OUTDATED** | Claim was likely true but code has changed | 0.0 |
| **UNVERIFIABLE** | Cannot find evidence to confirm or deny | Excluded from score |

---

## Scoring Formula

```
Document Score = (ACCURATE + 0.5 × PARTIAL) / (ACCURATE + PARTIAL + INACCURATE + OUTDATED) × 100%
```

Note: UNVERIFIABLE claims are excluded from the denominator as they cannot be assessed.

---

## Analysis Workflow

Execute these 7 phases sequentially. Use the TodoWrite tool to track progress through each phase.

### Phase 0: Load Fact Graph (if available)

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Load Fact Graph", "phase_number": 0, "total_phases": 6, "progress_percent": 0, "current_task": "Loading fact graph", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

**Objective**: Check for and load pre-generated fact graph to accelerate verification.

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
relations = []
facts = []
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

            # Load relations from all domain packs
            for pack_file in sorted(packs_dir.glob('*.relations.pack.json')):
                with open(pack_file) as f:
                    pack_data = json.load(f)
                    domain_relations = pack_data.get('relations', [])
                    relations.extend(domain_relations)
                    print(f"   Loaded {len(domain_relations)} relations from {pack_file.name}")

            # Load facts from all domain packs
            for pack_file in sorted(packs_dir.glob('*.facts.pack.json')):
                with open(pack_file) as f:
                    pack_data = json.load(f)
                    domain_facts = pack_data.get('facts', [])
                    facts.extend(domain_facts)
                    print(f"   Loaded {len(domain_facts)} facts from {pack_file.name}")

        fact_graph_loaded = True
        print(f"\n✅ Loaded fact graph: {len(entities)} entities, {len(relations)} relations, {len(facts)} facts")
        print(f"   Domains: {len(packs_metadata)}")
        for pack in packs_metadata:
            print(f"   - {pack['domain']}: {pack['entity_count']} entities, {pack['relation_count']} relations, {pack['fact_count']} facts")
    except Exception as e:
        print(f"⚠️ Failed to load fact graph: {e}")
        print("   Falling back to direct code verification")
        fact_graph_loaded = False
else:
    print("ℹ️ No fact graph found, using direct code verification")

# Helper functions for querying fact graph
def find_entities_by_type(entity_type):
    """Find all entities of a given type"""
    return [e for e in entities if e['type'] == entity_type]

def find_entity_by_name(name):
    """Find entity by exact name match"""
    return next((e for e in entities if e['name'] == name), None)

def find_facts_by_predicate(predicate):
    """Find all facts with a given predicate"""
    return [f for f in facts if f['predicate'] == predicate]

def find_relations_by_type(relation_type):
    """Find all relations of a given type"""
    return [r for r in relations if r['type'] == relation_type]

def get_entity_by_id(entity_id):
    """Get entity by ID"""
    return next((e for e in entities if e['id'] == entity_id), None)

# Build lookup indexes
entities_by_name = {e['name'].lower(): e for e in entities}
entities_by_type = {}
for entity in entities:
    entity_type = entity['type']
    if entity_type not in entities_by_type:
        entities_by_type[entity_type] = []
    entities_by_type[entity_type].append(entity)
```

**Usage in Phase 3 (Verification):**

When fact-graph is loaded, use it to accelerate claim verification:

```python
if fact_graph_loaded:
    # ARCHITECTURE CLAIMS: Use index metadata
    documented_architecture = extract_architecture_claim(doc)  # e.g., "MVC pattern"
    actual_project_type = index_metadata.get('project_type')
    actual_architecture = index_metadata.get('architecture_pattern')

    if documented_architecture == actual_architecture:
        status = "ACCURATE"
    else:
        status = "INACCURATE"

    # TECHNOLOGY CLAIMS: Use index statistics
    documented_tech = extract_tech_claim(doc)  # e.g., "Python 3.9"
    actual_languages = statistics.get('languages', {})

    # DATA MODEL CLAIMS: Use entities
    documented_entity = extract_entity_claim(doc)  # e.g., "User entity"
    if documented_entity.lower() in entities_by_name:
        entity = entities_by_name[documented_entity.lower()]
        status = "ACCURATE"
        evidence = f"{entity['file']}:{entity['line_range'][0]}"
    else:
        status = "INACCURATE"

    # API CLAIMS: Use endpoint entities
    documented_endpoint = extract_api_claim(doc)  # e.g., "POST /api/users"
    endpoints = entities_by_type.get('endpoint', [])
    matching_endpoint = next((e for e in endpoints if e['name'] == documented_endpoint), None)

    # BUSINESS RULES CLAIMS: Use facts
    documented_rule = extract_rule_claim(doc)  # e.g., "email is required"
    validation_facts = find_facts_by_predicate('validates')
    rule_found = any(documented_rule in str(f) for f in validation_facts)

    # INTEGRATION CLAIMS: Use integration facts
    documented_integration = extract_integration_claim(doc)  # e.g., "Integrates with Stripe"
    integration_facts = find_facts_by_predicate('integrates_with')

else:
    # Fallback to grep/glob for verification
    # ... original verification logic ...
```

**Benefits:**
- ✅ Instant access to all entities, relations, facts for verification
- ✅ No grep operations needed for entity/endpoint/table verification
- ✅ Architecture and technology stack pre-extracted in index
- ✅ Fast O(1) lookups vs O(N) grep searches
- ✅ Eliminates redundant grep operations
- ✅ Consistent verification across all claim categories

---

### Phase 1: Document Discovery

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Document Discovery", "phase_number": 1, "total_phases": 6, "progress_percent": 16, "current_task": "Discovering documentation files", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

**Objective**: Identify all LegacyLift documentation files to review.

#### 1.1 Locate Documentation

```
IF docs_path is provided:
    Use docs_path directly
ELSE:
    Search for common documentation folders in order:
    1. {code_path}/legacylift-docs/
    2. {code_path}/TXT/
    3. {code_path}/docs/
    4. {code_path}/documentation/
```

#### 1.2 Identify LegacyLift Documents

Look for the standard LegacyLift documentation files:

| File | Document Type |
|------|---------------|
| `00-EXECUTIVE-SUMMARY.md` | Executive Summary |
| `01-SYSTEM-ARCHITECTURE.md` | System Architecture |
| `02-DATA-MODEL-AND-RELATIONSHIPS.md` | Data Model |
| `03-BUSINESS-RULES-AND-REQUIREMENTS.md` | Business Rules |
| `04-INTEGRATION-AND-API-GUIDE.md` | Integration & API |
| `05-QUICK-REFERENCE.md` | Quick Reference |
| `06-GAP-ANALYSIS-REPORT.md` | Gap Analysis (optional) |

Also include any other `.md` files found in the documentation directory.

#### 1.3 Discovery Output

```
Documentation Files Found: X
- 00-EXECUTIVE-SUMMARY.md (found/not found)
- 01-SYSTEM-ARCHITECTURE.md (found/not found)
- 02-DATA-MODEL-AND-RELATIONSHIPS.md (found/not found)
- 03-BUSINESS-RULES-AND-REQUIREMENTS.md (found/not found)
- 04-INTEGRATION-AND-API-GUIDE.md (found/not found)
- 05-QUICK-REFERENCE.md (found/not found)
- Additional files: [list]
```

---

### Phase 2: Claim Extraction

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Claim Extraction", "phase_number": 2, "total_phases": 6, "progress_percent": 33, "current_task": "Extracting verifiable claims", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

**Objective**: Parse documentation to extract verifiable technical claims.

#### 2.1 What Constitutes a Claim

A **verifiable claim** is a statement that can be confirmed or denied by examining the code:

**Verifiable Claims** (extract these):
- "The system uses PostgreSQL for data persistence"
- "User passwords are hashed using bcrypt"
- "The API returns 404 when a resource is not found"
- "Orders have a status field with values: pending, processing, completed, cancelled"
- "Authentication uses JWT tokens with 24-hour expiry"

**Non-Verifiable Statements** (skip these):
- "The system is designed for scalability"
- "This approach improves maintainability"
- "The architecture follows best practices"
- Subjective descriptions or opinions

#### 2.2 Extraction by Document Type

**01-SYSTEM-ARCHITECTURE.md**:
- Architecture patterns mentioned (MVC, microservices, event-driven, etc.)
- Technology stack components
- Service/component names and their relationships
- Communication protocols between components
- Directory structure claims

**02-DATA-MODEL-AND-RELATIONSHIPS.md**:
- Entity/table names
- Field/column names and types
- Relationships (one-to-many, many-to-many, etc.)
- Constraints (unique, not null, foreign keys)
- Enum values

**03-BUSINESS-RULES-AND-REQUIREMENTS.md**:
- Validation rules
- Workflow steps
- Calculation formulas
- Threshold values
- Conditional logic

**04-INTEGRATION-AND-API-GUIDE.md**:
- Endpoint paths and methods
- Request/response formats
- Authentication methods
- External service integrations
- Error codes and messages

**00-EXECUTIVE-SUMMARY.md & 05-QUICK-REFERENCE.md**:
- Technology mentions
- High-level architecture claims
- Key feature descriptions

#### 2.3 Claim Recording Format

For each claim extracted, record:

| Field | Description |
|-------|-------------|
| Claim ID | Unique identifier (e.g., CLM-001) |
| Category | Architecture / Technology / Data Model / API / Business Rules / Integration |
| Document | Source document name |
| Line Number | Line where claim appears |
| Claim Text | The exact claim statement |
| Verification Approach | How to verify (search pattern, file to check, etc.) |

#### 2.4 Extraction Output

```
Claims Extracted: N
By Category:
- Architecture: X
- Technology: X
- Data Model: X
- API: X
- Business Rules: X
- Integration: X

By Document:
- 01-SYSTEM-ARCHITECTURE.md: X claims
- 02-DATA-MODEL-AND-RELATIONSHIPS.md: X claims
...
```

---

### Phase 3: Verification

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Verification", "phase_number": 3, "total_phases": 6, "progress_percent": 50, "current_task": "Verifying claims against codebase", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

**Objective**: Check each claim against the actual codebase.

**⚠️ IMPORTANT**: If fact-graph was loaded in Phase 0, use it as the primary verification source. This eliminates most grep operations and provides instant verification for entity/endpoint/table claims.

#### 3.1 Verification Strategy by Category

**Architecture Claims**:
- **If fact-graph loaded**: Use `index_metadata.get('project_type')` and `index_metadata.get('architecture_pattern')`
- **Fallback**: Search for mentioned patterns in code structure, look for framework/library imports
- Check directory structure
- Verify component/service existence via entities

**Technology Claims**:
- **If fact-graph loaded**: Use `statistics.get('languages')` for language breakdown
- **Fallback**: Check `package.json`, `requirements.txt`, `pom.xml`, etc.
- Look for import statements
- Search configuration files
- Verify version numbers in dependency files

**Data Model Claims**:
- **If fact-graph loaded**: Use `entities_by_name` dictionary for O(1) entity lookup
- **If fact-graph loaded**: Use `find_facts_by_predicate('has_property')` for field verification
- **Fallback**: Search for model/entity definitions, check migration files
- Look for schema definitions
- Verify field types and constraints

**API Claims**:
- **If fact-graph loaded**: Use `entities_by_type.get('endpoint')` for endpoint verification
- **If fact-graph loaded**: Use `find_facts_by_predicate('http_method')` for HTTP method verification
- **Fallback**: Search for route/endpoint definitions, check HTTP method handlers
- Verify request/response shapes
- Look for error handling

**Business Rules Claims**:
- **If fact-graph loaded**: Use `find_facts_by_predicate('validates')`, `find_facts_by_predicate('business_rule')`
- **If fact-graph loaded**: Use `find_facts_by_predicate('is_required')`, `find_facts_by_predicate('max_length')` for validation rules
- **Fallback**: Search for validation logic, look for conditional statements
- Check calculation implementations
- Verify threshold values

**Integration Claims**:
- **If fact-graph loaded**: Use `find_facts_by_predicate('integrates_with')` for external service verification
- **If fact-graph loaded**: Use `find_facts_by_predicate('authenticates_via')` for auth method verification
- **Fallback**: Search for external service client code, look for API keys/configuration
- Check webhook handlers
- Verify authentication implementations

#### 3.2 Verification Process

For each claim:

1. **Identify search patterns** based on claim content
2. **Use Grep/Glob** to find relevant code locations
3. **Read relevant files** to understand implementation
4. **Compare** documented claim against actual code
5. **Assign status**: ACCURATE, PARTIAL, INACCURATE, OUTDATED, or UNVERIFIABLE
6. **Document evidence**: File path, line number, relevant code snippet

#### 3.3 Evidence Requirements

| Status | Required Evidence |
|--------|-------------------|
| ACCURATE | Code snippet that confirms the claim |
| PARTIAL | Code showing what matches and what doesn't |
| INACCURATE | Code that contradicts the claim |
| OUTDATED | Evidence of change (different implementation, deprecated code) |
| UNVERIFIABLE | List of search patterns tried and locations checked |

#### 3.4 Verification Output

For each claim:
```
Claim: CLM-001
Category: Technology
Status: ACCURATE
Evidence:
  File: requirements.txt
  Line: 12
  Code: fastapi==0.95.0
  Notes: Version matches documented claim
```

---

### Phase 4: Scoring

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Scoring", "phase_number": 4, "total_phases": 6, "progress_percent": 66, "current_task": "Calculating accuracy scores", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

**Objective**: Calculate accuracy scores per document and category.

#### 4.1 Document Scores

For each document, calculate:

```
Verified Claims = ACCURATE + PARTIAL + INACCURATE + OUTDATED
(excludes UNVERIFIABLE)

Score = (ACCURATE + 0.5 × PARTIAL) / Verified Claims × 100%
```

#### 4.2 Category Scores

For each category across all documents:

```
Category Score = Sum(category claims scored) / Total category verified claims × 100%
```

#### 4.3 Overall Score

```
Overall Score = Total weighted score / Total verified claims × 100%
```

#### 4.4 Score Interpretation

| Score Range | Interpretation |
|-------------|----------------|
| 95-100% | Excellent - Documentation highly accurate |
| 85-94% | Good - Minor inaccuracies, mostly reliable |
| 70-84% | Fair - Several inaccuracies, review recommended |
| 50-69% | Poor - Significant inaccuracies, update needed |
| <50% | Critical - Documentation unreliable, major revision required |

#### 4.5 Scoring Output

```
DOCUMENT SCORES:
| Document | Accurate | Partial | Inaccurate | Outdated | Unverifiable | Score |
|----------|----------|---------|------------|----------|--------------|-------|
| 01-SYSTEM-ARCHITECTURE.md | 15 | 3 | 2 | 0 | 1 | 82.5% |
...

CATEGORY SCORES:
| Category | Accurate | Partial | Inaccurate | Outdated | Score |
|----------|----------|---------|------------|----------|-------|
| Architecture | 10 | 2 | 1 | 0 | 84.6% |
...

OVERALL SCORE: XX.X%
```

---

### Phase 5: Report Generation

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Report Generation", "phase_number": 5, "total_phases": 6, "progress_percent": 83, "current_task": "Generating accuracy report", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

**Objective**: Generate the comprehensive accuracy report.

#### 5.1 Report Structure

Use the template at `templates/07-DOCUMENTATION-ACCURACY-REPORT.md` and fill in:

1. **Executive Summary**: Overall score, key findings, score distribution
2. **Part 1 - Accuracy by Document**: Scorecard for each document
3. **Part 2 - Accuracy by Category**: Scores per claim category
4. **Part 3 - Critical Findings**: CRITICAL and HIGH severity issues
5. **Part 4 - Detailed Findings**: All verification results
6. **Part 5 - Recommendations**: Prioritized corrections
7. **Appendices**: Methodology, claim inventory

#### 5.2 Severity Assignment

Assign severity based on impact:

| Severity | Criteria |
|----------|----------|
| CRITICAL | Core architecture or technology claim is wrong |
| HIGH | API endpoint, data model, or business rule is incorrect |
| MEDIUM | Partial inaccuracy or missing details |
| LOW | Minor discrepancy, cosmetic issue |

#### 5.3 Findings Format

Each finding should include:
- Claim ID and text
- Document source and line
- Expected (per documentation)
- Actual (per code)
- Evidence (file:line, code snippet)
- Severity and recommended action

---

### Phase 6: Output

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Output", "phase_number": 6, "total_phases": 6, "progress_percent": 95, "current_task": "Writing final report", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

**Objective**: Write the final report to the output directory.

#### 6.1 Output File

Write to `{output_dir}/07-DOCUMENTATION-ACCURACY-REPORT.md`

#### 6.2 Final Checklist

Before completing, verify:
- [ ] All sections of template are filled
- [ ] All findings include evidence citations
- [ ] Statistics are accurate and consistent
- [ ] Tables are properly formatted
- [ ] Mermaid diagrams have valid syntax
- [ ] Recommendations are actionable
- [ ] Document ends with footer: `---\n\n*Generated By LegacyLift AI by CapTech*`

#### 6.3 Completion Message

```
Documentation Accuracy Review Complete!

Report written to: {output_dir}/07-DOCUMENTATION-ACCURACY-REPORT.md

Summary:
- Documents Reviewed: X
- Claims Verified: Y
- Overall Accuracy: Z%

Findings:
- CRITICAL: N
- HIGH: N
- MEDIUM: N
- LOW: N

Next Steps:
1. Review the report
2. Address CRITICAL and HIGH findings first
3. Update documentation to correct inaccuracies
4. Re-run /legacylift-classic:documentation-review to verify fixes
```

---

## Error Handling

| Error | Handling |
|-------|----------|
| Documentation folder not found | Report error, list paths checked |
| No LegacyLift docs found | Report, suggest running documentation skills first |
| Code path invalid | Report error, ask user to specify valid path |
| File read errors | Log warning, continue with other files |
| No verifiable claims found | Report, document may be too high-level |

---

## Supporting Files & Templates

This skill uses supporting files in the `templates/` directory to ensure consistent, high-quality documentation output.

### Template Structure

| Template File | Purpose | Usage |
|---------------|---------|-------|
| **[07-DOCUMENTATION-ACCURACY-REPORT.md](./templates/07-DOCUMENTATION-ACCURACY-REPORT.md)** | Structure for documentation accuracy report | Guides semantic accuracy validation of documentation against codebase |

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
| 07 | [DOCUMENTATION-ACCURACY-REPORT](./templates/07-DOCUMENTATION-ACCURACY-REPORT.md) ⭐ | **documentation-review** | Documentation accuracy validation |
| 08 | USE-CASES-{DOMAIN} | use-case-generator | Comprehensive use case documentation |
| 09 | CITATION-VALIDATION-REPORT | citation-validator | Citation correctness validation |
| 10 | GAP-ANALYSIS-REPORT | gap-analyzer | Documentation-code gap analysis |

⭐ = Generated by this skill

---

## Output Example

See `templates/07-DOCUMENTATION-ACCURACY-REPORT.md` for the complete output format.

---

*Generated By LegacyLift AI by CapTech*
