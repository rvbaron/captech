---
name: database-layer-documenter
description: Analyzes database layer by domain to extract business logic, key tables, and relationships for modernization planning. Generates domain-specific documentation focused on what development teams need to migrate legacy applications.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, BashOutput, Task, TodoWrite, Skill, WebFetch
---

# Database Layer Documenter

This skill performs **modernization-focused analysis** of database layer artifacts and generates domain-specific documentation for development teams planning legacy application migrations.

## Instructions

The database-layer-documenter skill systematically analyzes database artifacts by domain and produces domain-specific documentation files:

**02-DATA-MODEL-AND-RELATIONSHIPS-[DOMAIN].md** - Domain-specific database documentation (60-75 min read each)

Output files are placed directly in the `legacylift-docs/` folder.

## Examples

```
Use the database-layer-documenter skill on this repository.
```

```
Update the database layer documentation with database-layer-documenter.
```

```
Analyze a specific domain with database-layer-documenter.
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

## What Gets Analyzed

**Important Note**: This skill generates **modernization-focused documentation** that describes key tables, business logic, and relationships needed for migration planning. It is **NOT a complete data dictionary** with exhaustive field-level definitions. The documentation focuses on understanding business logic, patterns, and relationships rather than cataloging every column in every table.

This skill focuses on **database artifacts relevant to modernization**:

### 📊 **Core Domain Tables**
- ✅ Key business entity tables in the domain
- ✅ Table purpose and role in domain
- ✅ Important columns and their meaning
- ✅ Primary keys and foreign key relationships
- ✅ Unique business constraints

### 🔗 **Domain Relationships**
- ✅ Relationships between domain tables
- ✅ Cross-domain relationships and dependencies
- ✅ Foreign key constraints and cascade rules
- ✅ Junction tables for many-to-many relationships
- ✅ Referential integrity patterns

### ⚡ **Business Logic in Database Layer**
- ✅ **Stored procedures containing business rules** (not simple CRUD)
- ✅ Complex calculations and transformations
- ✅ Workflow orchestration in procedures
- ✅ Data validation logic
- ✅ Integration and ETL procedures
- ✅ Dependencies between procedures

### ⚙️ **Triggers (Hidden Business Rules)**
- ✅ Audit trail triggers
- ✅ Business rule enforcement triggers
- ✅ Cascade operations and side effects
- ✅ Data validation triggers
- ✅ Impact on data operations

### 📐 **Functions**
- ✅ Scalar functions with business logic
- ✅ Table-valued functions for data access
- ✅ Usage patterns and dependencies
- ✅ Reusable calculations

### 👁️ **Views**
- ✅ Views abstracting domain data
- ✅ Security and access control views
- ✅ Reporting and aggregation views
- ✅ Underlying table dependencies

### 🔄 **Integration Points**
- ✅ Staging tables for external systems
- ✅ Integration procedures
- ✅ Data exchange patterns
- ✅ ETL and batch processing logic

## Documentation Process

The skill follows a systematic 5-phase approach:

**⚠️ CRITICAL: Citations are NOT a post-processing step. Every claim must be cited AS YOU WRITE IT. Never write prose first and add citations later.**

### Phase 0: Load Fact Graph (if available)

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Load Fact Graph", "phase_number": 0, "total_phases": 4, "progress_percent": 0, "current_task": "Checking for fact graph", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

**Objective**: Check for and load pre-generated fact graph to avoid redundant code analysis.

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
        print("   Falling back to direct code analysis")
        fact_graph_loaded = False
else:
    print("ℹ️ No fact graph found, using direct code analysis")

# Helper functions for querying fact graph
def find_entities_by_type(entity_type):
    """Find all entities of a given type"""
    return [e for e in entities if e['type'] == entity_type]

def find_entities_by_domain(domain):
    """Find all entities in a given domain"""
    return [e for e in entities if e.get('attributes', {}).get('domain') == domain]

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

def get_domains():
    """Get list of all domains from packs metadata"""
    return [pack['domain'] for pack in packs_metadata]

def get_domain_statistics(domain):
    """Get statistics for a specific domain"""
    return next((pack for pack in packs_metadata if pack['domain'] == domain), None)

def find_entity_facts(entity_id):
    """Find all facts for a given entity"""
    return [f for f in facts if f['subject_id'] == entity_id]

def find_entity_relations(entity_id, relation_type=None):
    """Find all relations involving an entity"""
    rels = [r for r in relations if r['source_id'] == entity_id or r['target_id'] == entity_id]
    if relation_type:
        rels = [r for r in rels if r['type'] == relation_type]
    return rels
```

**Usage in Subsequent Phases:**
```python
if fact_graph_loaded:
    # Use fact graph data
    tables = find_entities_by_type('table')
    stored_procs = find_entities_by_type('stored_proc')
    triggers = find_entities_by_type('trigger')
    views = find_entities_by_type('view')
    sql_functions = find_entities_by_type('sql_function')

    # Get columns for a table
    table_id = tables[0]['id']
    columns = [f for f in facts if f['subject_id'] == table_id and f['predicate'] == 'has_column']

    # Get procedure dependencies
    proc_id = stored_procs[0]['id']
    reads = find_entity_relations(proc_id, 'reads_from')
    writes = find_entity_relations(proc_id, 'writes_to')
else:
    # Fallback to direct DDL file analysis
    # ... original grep/glob commands ...
```

### Phase 1: Domain Discovery & Analysis

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Domain Discovery & Analysis", "phase_number": 1, "total_phases": 4, "progress_percent": 25, "current_task": "Discovering database domains", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

**If fact-graph is loaded:**
- Query entities by type to identify domain scope:
  - Tables: `find_entities_by_type('table')`
  - Stored procedures: `find_entities_by_type('stored_proc')`
  - Views: `find_entities_by_type('view')`
  - Functions: `find_entities_by_type('sql_function')`
  - Triggers: `find_entities_by_type('trigger')`
- Filter entities by domain using `find_entities_by_domain(domain_name)`
- Get domain statistics from `get_domain_statistics(domain_name)`
- Use entity attributes and annotations to identify business logic procedures

**If fact-graph is not loaded (fallback):**
- Scan DDL files to identify domain scope (tables, procedures, views, functions, triggers)
- Analyze key domain tables and their relationships using Grep/Read
- Identify business logic in stored procedures (skip simple CRUD)
- Find triggers, functions, and views relevant to domain
- Identify cross-domain dependencies
- Detect integration patterns and staging tables

### Phase 2: Business Logic Extraction

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Business Logic Extraction", "phase_number": 2, "total_phases": 4, "progress_percent": 50, "current_task": "Extracting business logic from database layer", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

- Extract business rules from stored procedures
- Document trigger logic and side effects
- Identify functions with business calculations
- Document check constraints and validation rules
- Map workflows implemented in database layer
- Identify data transformation logic

### Phase 3: Relationship & Dependency Mapping

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Relationship & Dependency Mapping", "phase_number": 3, "total_phases": 4, "progress_percent": 75, "current_task": "Mapping domain relationships", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

**If fact-graph is loaded:**
- Query foreign_key relations for domain ERD: `find_relations_by_type('foreign_key')`
- Map relationships within domain using relations between domain entities
- Document cross-domain relationships by checking target entities in other domains
- Map procedure-to-table dependencies:
  - For each stored procedure: `find_entity_relations(proc_id, 'reads_from')`
  - For each stored procedure: `find_entity_relations(proc_id, 'writes_to')`
- Document trigger-to-table associations using entity relations
- Identify view dependencies using entity relations and facts

**If fact-graph is not loaded (fallback):**
- Parse DDL files to create domain ERD with all tables
- Map relationships within domain using foreign key definitions
- Document cross-domain relationships
- Parse stored procedure SQL to map procedure-to-table dependencies
- Document trigger-to-table associations from trigger DDL
- Identify view dependencies from view definitions

### Phase 4: Document Generation with Inline Citations

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Document Generation", "phase_number": 4, "total_phases": 4, "progress_percent": 95, "current_task": "Generating documentation with citations", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

**CRITICAL: Write WITH citations from the start, not added later.**

For each section:
1. **Plan**: Outline what to document
2. **Search**: Find relevant entities/facts/relations in fact-graph (if loaded) OR find DDL files (fallback)
3. **Write**: Compose WITH inline citations as you write
4. **Validate**: Every table, procedure, constraint has citations

**Citation Standards (using fact-graph evidence when available)**:
- Table definitions → use entity evidence: `entity['file']` and `entity['line_range']`
- Stored procedures → use entity evidence from stored_proc entities
- Constraints → use fact evidence from constraint facts (is_required, is_unique, etc.)
- Triggers → use entity evidence from trigger entities
- Relationships → use relation evidence from foreign_key relations
- Business logic → use fact evidence from business_rule facts or procedure entity location

**If fact-graph loaded:**
```python
# Example: Get citation for a table
table = find_entity_by_name('Orders')
file_path = table['file']
line_range = table['line_range']
citation = f"[📄]({file_path}:{line_range[0]})"

# Example: Get citation for a foreign key
fk_relations = find_relations_by_type('foreign_key')
for fk in fk_relations:
    evidence = fk['evidence'][0]  # First evidence entry
    file_path = evidence['file']
    line_range = evidence['line_range']
    citation = f"[📄]({file_path}:{line_range[0]})"
```

**If fact-graph not loaded (fallback):**
- Table definitions → cite DDL file with line number
- Stored procedures → cite procedure file with line number
- Constraints → cite DDL constraint definition
- Triggers → cite trigger DDL
- Relationships → cite FK constraint definitions
- Business logic → cite procedure/function implementation

All documentation includes:
- **Domain-focused coverage** - Key tables, business logic, and relationships
- **Mermaid ERD diagrams** - Complete domain relationship diagrams
- **Inline citations** - Every claim backed by DDL file reference
- **Cross-references** - Dependencies clearly mapped
- **Business logic extraction** - Rules from database layer documented
- **Migration guidance** - Patterns and recommendations for modernization

---

## Incremental Document Writing Process

**⚠️ MANDATORY: All database layer documentation must be written incrementally to manage context efficiently and avoid token limits.**

### Why Incremental Writing?
- Database domains can have 20-50+ tables with extensive stored procedures
- Reading the full file before each append wastes tokens
- Incremental writing allows indefinite document length
- More efficient and reliable for comprehensive documentation

### Initial Setup

1. **Create the initial document** with:
   - Front matter (title, domain name, audience, reading time, table of contents)
   - Domain Overview section
   - First 5-10 tables with full documentation
   - Add marker at the end: `<!-- MORE CONTENT TO FOLLOW -->`

Example:
```markdown
# Database Layer Documentation: Claims Management Domain
[front matter...]
## Core Domain Tables
### Table: Claims
[full table documentation with citations...]
### Table: ClaimLineItems
[full table documentation with citations...]
[... continue for first 5-10 tables ...]
<!-- MORE CONTENT TO FOLLOW -->
```

### For Each Additional Section

2. **Use the Edit tool** to replace the marker with new content:
   - **old_string**: `<!-- MORE CONTENT TO FOLLOW -->`
   - **new_string**: `[NEXT SET OF TABLES/PROCEDURES/SECTION]\n\n<!-- MORE CONTENT TO FOLLOW -->`

3. **DO NOT read the full file** before appending - the Edit tool will find and replace the marker

4. **For each batch of tables/procedures you write:**
   - Search for DDL files FIRST using Glob/Grep or direct file reads
   - Gather all table definitions, constraints, and relationships BEFORE writing prose
   - Write the table documentation WITH inline citations as you compose each description
   - Never write a table description, column purpose, or constraint without immediately adding its citation
   - Replace the marker and continue to the next batch

### Writing Pattern for Database Documentation

```
For each batch of tables (5-10 tables at a time):
1. Search NOW: Find DDL files for these tables
2. Gather citations: Collect file:line references for:
   - Table definitions
   - Column definitions
   - Primary/foreign keys
   - Check constraints
   - Indexes
   - Triggers
3. Write WITH citations:
   - Table purpose [📄](DDL-file:line)
   - Key columns [📄](DDL-file:line)
   - Relationships [📄](FK-constraint:line)
   - Constraints [📄](constraint-definition:line)
4. Replace marker with: table batch content + marker
5. Move to next batch
```

### Recommended Section Breakdown

Write the document in these increments (replace marker after each):
1. **Front Matter + Domain Overview + First 5-10 Tables** (~300-400 lines)
2. **Next 10-15 Tables** (~200-300 lines per batch)
3. **Remaining Tables** (continue batching)
4. **Stored Procedures with Business Logic** (~200-300 lines)
5. **Triggers and Functions** (~100-200 lines)
6. **Views** (~100-150 lines)
7. **Domain ERD Diagram** (Mermaid diagram)
8. **Cross-Domain Relationships** (~100-150 lines)
9. **Migration Recommendations + Footer** (final section, remove marker)

### Final Step

5. **Remove the marker** when writing the last section (Migration Recommendations, Related Documents, Footer)
   - **old_string**: `<!-- MORE CONTENT TO FOLLOW -->`
   - **new_string**: `[FINAL SECTION CONTENT]\n\n---\n\n*Generated By LegacyLift AI by CapTech*`

### Key Rules

- ✅ Write tables/procedures in batches incrementally
- ✅ Replace the marker each time using Edit tool (don't read the whole file)
- ✅ Generate citations DURING writing (not after)
- ✅ Search for DDL files BEFORE writing each batch
- ✅ Use Edit tool with exact marker text for find/replace
- ❌ DO NOT read the entire file between batches
- ❌ DO NOT write table descriptions first and add citations later
- ❌ DO NOT skip the marker (always add it until the final section)
- ❌ DO NOT try to document all 50+ tables in one pass

### Example Workflow

```
1. Write: Front matter + Overview + Tables 1-10 + marker
2. Edit: Replace marker with Tables 11-20 + marker
3. Edit: Replace marker with Tables 21-30 + marker
4. Edit: Replace marker with Remaining Tables + marker
5. Edit: Replace marker with Stored Procedures + marker
6. Edit: Replace marker with Triggers + marker
7. Edit: Replace marker with Views + marker
8. Edit: Replace marker with ERD Diagram + marker
9. Edit: Replace marker with Cross-Domain Relationships + marker
10. Edit: Replace marker with Migration Recommendations + footer (no marker)
```

### Token Efficiency

This approach:
- Keeps context usage minimal (only marker location needed, not full file)
- Allows documentation of large database domains (50+ tables, 100+ procedures)
- Maintains citation quality throughout
- Prevents context window exhaustion
- Enables comprehensive coverage without token limit issues

---

## Key Features

### 🎯 **Modernization-Focused Coverage**
This skill documents database artifacts relevant to migration:
- **Core domain tables** (not every lookup/trivial table)
- **Business logic procedures** (complex rules, not simple CRUD)
- **All triggers** (often hidden business rules)
- **Functions with business logic** (calculations, transformations)
- **Views** (data access patterns)
- **Key constraints** (business rules enforced in database)

### 📊 **Table Documentation**
For each core domain table, document:
- Table purpose and role in domain
- Key columns and their meaning
- Primary and foreign key relationships
- Business constraints (check constraints, unique constraints)
- Relationship to other domain tables

### 🔍 **Business Logic Procedure Analysis**
For procedures with business logic, document:
- Purpose and business function
- Key business rules and validations
- Tables accessed and operations performed
- Data transformations and calculations
- Integration points
- Dependencies on other procedures/functions

### 🗺️ **Domain Relationship Mapping**
- Complete domain ERD with all domain tables
- Foreign key relationships with cardinality
- Cross-domain relationships
- Procedure-to-table dependencies
- Trigger associations
- View dependencies

### 💡 **Business Logic Extraction**
- Identify business rules enforced in database layer
- Extract validation logic from check constraints
- Document calculations from procedures
- Map workflow implementations
- Identify integration logic
- Document data transformation patterns

### 🏗️ **Migration Guidance**
- Naming convention analysis
- Design pattern identification (temporal, audit, soft delete)
- Data access pattern analysis
- Integration pattern documentation
- Anti-pattern identification
- Technical debt assessment
- Modernization recommendations

## Output Quality Standards

All generated documentation includes:

✅ **Modernization-Focused Coverage** - Key tables, business logic, and relationships
✅ **Table of Contents** - Hierarchical navigation structure
✅ **Estimated Reading Times** - 60-75 minutes per domain
✅ **Target Audience** - Development teams, architects, data engineers planning migrations
✅ **Mermaid ERD Diagrams** - Complete domain relationship diagrams
✅ **Inline Citations** - Every claim cited with DDL file and line number
✅ **Dependency Documentation** - Procedure, trigger, view, and table dependencies
✅ **Business Logic Extraction** - Rules from database layer documented
✅ **Migration Guidance** - Patterns, anti-patterns, and recommendations
✅ **Cross-Domain References** - How this domain relates to others
✅ **Domain Statistics** - Object counts and complexity metrics

## Domain Structure

**Domains are identified from the existing 02-DATA-MODEL-AND-RELATIONSHIPS.md file in the legacylift-docs/ folder.**

The skill reads the **"Core Domain Entities"** section from the existing [02-DATA-MODEL-AND-RELATIONSHIPS.md](../../legacylift-docs/02-DATA-MODEL-AND-RELATIONSHIPS.md) file to determine which domains exist in the database. Each domain listed in that section will receive its own comprehensive documentation file.

If the 02-DATA-MODEL-AND-RELATIONSHIPS.md file does not exist, the skill will analyze table naming patterns to automatically identify logical domains (e.g., by table prefix patterns, schema names, or functional groupings).

## Example Output Structure

```
legacylift-docs/
├── 02-DATA-MODEL-AND-RELATIONSHIPS_DOMAIN_1.md
│   ├── 1. Domain Overview (statistics, purpose, scope)
│   ├── 2. Domain ERD Diagram
│   ├── 3. Core Domain Tables (purpose, key columns, relationships)
│   ├── 4. Business Logic in Database Layer (procedures, triggers, functions)
│   ├── 5. Views & Data Access Patterns
│   ├── 6. Integration Points (staging tables, integration procedures)
│   ├── 7. Cross-Domain Relationships
│   └── 8. Migration Considerations
├── 02-DATA-MODEL-AND-RELATIONSHIPS_DOMAIN_2.md
├── 02-DATA-MODEL-AND-RELATIONSHIPS_DOMAIN_3.md
└── ... (one file per domain)
```

## Success Criteria

Documentation is considered complete when:

✅ **Core domain tables documented** with purpose, key columns, and relationships
✅ **Business logic procedures analyzed** with rules and dependencies
✅ **All triggers documented** with logic and effects
✅ **Functions with business logic documented** with purpose and dependencies
✅ **Views documented** with purpose and dependencies
✅ **Key business constraints listed** with validation rules
✅ **Domain ERD created** showing all tables and relationships
✅ **Cross-domain dependencies documented**
✅ **All claims cited** - DDL files with line numbers
✅ **Business logic extracted** from database layer
✅ **Patterns identified** - design patterns, anti-patterns
✅ **Migration guidance provided** - recommendations for modernization

## Skill Execution

When this skill is invoked, I will:

1. **Clarify the Scope** (if needed)
   - Database folder location (DDL files path)
   - Specific domain to analyze (or ALL domains)
   - Confirm output location (legacylift-docs/)

2. **Identify Domains**
   - Read the existing [02-DATA-MODEL-AND-RELATIONSHIPS.md](../../legacylift-docs/02-DATA-MODEL-AND-RELATIONSHIPS.md) file to extract domains from the "Core Domain Entities" section
   - If that file doesn't exist, scan all tables and categorize by naming patterns (prefixes, schemas, functional groupings)
   - If specific domain requested, focus only on that domain
   - If no domains are specified, analyze and document all identified domains

3. **Create Domain-Specific Todo List** (per domain)
   - Phase 0: Load Fact Graph (if available)
   - Phase 1: Domain Discovery & Inventory
   - Phase 2: Table Structure Analysis (ALL tables in domain)
   - Phase 3: Related Stored Procedures (procedures operating on domain tables)
   - Phase 4: Domain-Specific Views, Triggers, Indexes
   - Phase 5: Domain Relationship Mapping (within and across domains)
   - Phase 6: Domain Business Logic Extraction
   - Phase 7: Generate Domain Documentation with Citations
   - Phase 8: Review & Validation

4. **Execute Domain-by-Domain** (or single domain if specified)
   - For each domain:
     * Gather all DDL for domain tables
     * Identify related procedures (up_insert[Domain]*, up_update[Domain]*, etc.)
     * Map relationships within domain and to other domains
     * Extract business logic from domain procedures
     * **Generate Domain-Specific Documentation**:
       - Write 02-DATA-MODEL-AND-RELATIONSHIPS_[DOMAIN].md
       - Include comprehensive citations
       - Focus on domain-specific patterns and dependencies
       - Create domain-specific ERD diagrams

5. **Deliver Domain Documentation Files**
   - One file per domain: 02-DATA-MODEL-AND-RELATIONSHIPS_[DOMAIN].md
   - Placed directly in legacylift-docs/ folder
   - Following domain-focused template structure
   - With domain-specific Mermaid ERD diagrams
   - **Every domain table/procedure documented with citations**
   - Cross-domain relationships clearly identified

6. **Provide Summary** (per domain or all domains)
   - Domain object counts (tables, procedures, views, triggers)
   - Domain complexity assessment
   - Key domain patterns identified
   - Cross-domain dependencies
   - Domain-specific technical debt
   - Domain migration recommendations

---

## Incremental Writing & Persistence Guidelines

**⚠️ MANDATORY: All long-form documentation must be written incrementally to manage context efficiently and avoid token limits.**

### Why Incremental Writing?

- Long documents (60+ min read, 1000+ lines) will exceed context windows if written all at once
- Reading the full file before each append wastes tokens
- Incremental writing allows indefinite document length
- More efficient and reliable for comprehensive documentation
- Your context window will be automatically compacted as it approaches its limit, allowing you to continue working indefinitely from where you left off

### Initial Document Setup

1. **Create the initial document** with:
   - Front matter (title, audience, reading time, table of contents)
   - Overview/introduction section
   - First 1-2 major sections with complete content and citations
   - Add marker at the end: `<!-- MORE CONTENT TO FOLLOW -->`

Example:
```markdown
# Document Title
[front matter, TOC...]

## Section 1: Introduction
[complete content with citations...]

## Section 2: First Major Topic
[complete content with citations...]

<!-- MORE CONTENT TO FOLLOW -->
```

### For Each Additional Section

2. **Use the Edit tool** to replace the marker with new content:
   - **old_string**: `<!-- MORE CONTENT TO FOLLOW -->`
   - **new_string**: `[NEW SECTION WITH COMPLETE CONTENT]\n\n<!-- MORE CONTENT TO FOLLOW -->`

3. **DO NOT read the full file** before appending - the Edit tool will find and replace the marker automatically

4. **For each section you write:**
   - Search for implementation evidence FIRST using Task/Explore or direct file reads
   - Gather all file paths and line numbers BEFORE writing prose
   - Write the section WITH inline citations as you compose each sentence
   - Never write content without immediately adding its citation
   - Replace the marker and continue to the next section

### Writing Pattern for Each Section

```
For each section or domain:
1. Search NOW: Find relevant source files, methods, classes, configurations
2. Gather citations: Collect file:line references for all claims
3. Write WITH citations inline:
   - Every technology claim → cite config file or import [📄](path:line)
   - Every feature → cite implementation [📄](path:line)
   - Every data entity → cite model class [📄](path:line)
   - Every business rule → cite validation logic [📄](path:line)
4. Replace marker with: section content + marker
5. Move to next section
```

### Recommended Section Breakdown

Write the document in these increments (replace marker after each):
1. **Front Matter + Overview** (~200-300 lines)
2. **Major Section 1** (~200-400 lines with citations)
3. **Major Section 2** (~200-400 lines with citations)
4. **Major Section 3+** (continue pattern, ~200-400 lines each)
5. **Supporting Sections** (diagrams, workflows, examples)
6. **Final Section + Footer** (remove marker, add footer)

### Final Step

5. **Remove the marker** when writing the last section:
   - **old_string**: `<!-- MORE CONTENT TO FOLLOW -->`
   - **new_string**: `[FINAL SECTION CONTENT]\n\n---\n\n*Generated By LegacyLift AI by CapTech*\n\n*Generated on: {GENERATED_DATETIME}*`
   - Replace `{GENERATED_DATETIME}` with the current date and time in ISO 8601 format (e.g., `2026-02-16T14:30:45Z`)

### Key Rules

- ✅ Write section-by-section incrementally
- ✅ Replace the marker each time using Edit tool (don't read the whole file)
- ✅ Generate citations DURING writing (not after)
- ✅ Search for evidence BEFORE writing each section
- ✅ Use Edit tool with exact marker text for find/replace
- ❌ DO NOT read the entire file between sections
- ❌ DO NOT write content first and add citations later
- ❌ DO NOT skip the marker (always add it until the final section)

### Persistence & Autonomy

**Your context window will be automatically compacted as it approaches its limit, allowing you to continue working indefinitely from where you left off. Therefore, do not stop tasks early due to token budget concerns.**

**Critical Requirements:**
- As you approach your token budget limit, save your current progress and state to memory before the context window refreshes
- Always be as persistent and autonomous as possible
- Complete tasks fully, even if the end of your budget is approaching
- Never artificially stop any task early regardless of the context remaining
- If context compaction occurs, resume exactly where you left off using the marker pattern
- The `<!-- MORE CONTENT TO FOLLOW -->` marker enables seamless continuation after context refresh

**Handling Context Compaction:**
1. Document current section/phase in todo list before context refresh
2. Ensure continuation marker is present in document
3. After refresh, use Edit tool to find marker (no need to read full file)
4. Continue with next section using the same incremental pattern
5. Maintain same format and quality standards throughout

---

### Token Efficiency

This approach:
- Keeps context usage minimal (only marker location needed, not full file)
- Allows documents of any length to be created
- Maintains citation quality throughout
- Prevents context window exhaustion
- Enables you to write 60+ min read documents without issues

---

## Supporting Files & Templates

This skill uses supporting files in the `templates/` directory to ensure consistent, comprehensive documentation output.

### Template Structure

| Template File | Purpose | Usage |
|---------------|---------|-------|
| **[02-DATA-MODEL-AND-RELATIONSHIPS.md](./templates/02-DATA-MODEL-AND-RELATIONSHIPS.md)** | Structure for domain-specific data model documentation | Guides comprehensive coverage of domain tables and relationships |

### LegacyLift Documentation Ecosystem

This skill is part of the comprehensive LegacyLift documentation suite. Here's the complete set of documents available:

| Prefix | Document | Generated By | Description |
|--------|----------|--------------|-------------|
| **Core Documentation Suite** ||||
| 00 | EXECUTIVE-SUMMARY | exec-summary-generator | High-level overview for all stakeholders |
| 01 | SYSTEM-ARCHITECTURE | si-documenter | Technical architecture deep dive |
| 02 | [DATA-MODEL-AND-RELATIONSHIPS](./templates/02-DATA-MODEL-AND-RELATIONSHIPS.md) ⭐ | data-documenter, **database-layer-documenter** | Data structures and relationships |
| 03 | BUSINESS-RULES-AND-REQUIREMENTS | business-documenter, detailed-req-documenter | Functional requirements and rules |
| 04 | INTEGRATION-AND-API-GUIDE | si-documenter | API documentation and integration patterns |
| 05 | QUICK-REFERENCE | si-documenter | Glossary and quick lookups |
| **Extended Documentation & Analysis** ||||
| 06 | TABLE-VALIDATION-* | table-validation | ORM mapping validation reports |
| 07 | DOCUMENTATION-ACCURACY-REPORT | documentation-review | Documentation accuracy validation |
| 08 | USE-CASES-{DOMAIN} | use-case-generator | Comprehensive use case documentation |
| 09 | CITATION-VALIDATION-REPORT | citation-validator | Citation correctness validation |
| 10 | GAP-ANALYSIS-REPORT | gap-analyzer | Documentation-code gap analysis |

⭐ = Generated by this skill (creates 02-DATA-MODEL-AND-RELATIONSHIPS-{DOMAIN}.md for each domain)

### How Templates Are Used

During skill execution, I will:

1. **Reference Template**: Read the 02-DATA-MODEL-AND-RELATIONSHIPS template
2. **Extract Structure**: Use the template's sections, headings, organization
3. **Fill with Analysis**: Replace placeholders with actual domain-specific DDL analysis
4. **Maintain Comprehensiveness**: Ensure ALL domain objects are covered
5. **Adapt per Domain**: Customize for domain-specific patterns and relationships
6. **Generate Multiple Files**: Create separate file for each domain

### Template Features

The template includes:

- **Instructional Comments**: HTML comments guiding complete coverage
- **Placeholder Syntax**: `{PLACEHOLDER}` markers for project-specific values
- **Section Organization**: Pre-structured for exhaustive documentation
- **Diagram Scaffolds**: Mermaid templates for ERDs and dependency graphs
- **Table Templates**: Structures for object catalogs and matrices
- **Citation Patterns**: Examples for DDL file references
- **Completeness Checklists**: Ensure no objects are missed

## Difference from data-documenter Skill

| Aspect | data-documenter | database-layer-documenter |
|--------|----------------|---------------------------|
| **Scope** | Conceptual data model | **Domain-specific database analysis** |
| **Table Coverage** | Core entities (12-15 tables) | **All domain tables** |
| **Stored Procedures** | Sample procedures, overview | **Business logic procedures (not simple CRUD)** |
| **Depth** | Conceptual relationships | **Implementation details from DDL** |
| **Focus** | Application data structures | **Database layer for migration** |
| **Audience** | Software engineers, architects | **Development teams, data engineers** |
| **Business Logic** | Application-layer logic | **Database-layer logic (procedures, triggers)** |
| **Output** | Single consolidated file | **Multiple domain-specific files** |
| **Read Time** | 50-60 minutes | **60-75 minutes per domain** |
| **File Naming** | 02-DATA-MODEL-AND-RELATIONSHIPS.md | **02-DATA-MODEL-AND-RELATIONSHIPS_[DOMAIN].md** |

Use **data-documenter** for: Understanding conceptual data structures and application-level relationships

Use **database-layer-documenter** for: Deep domain analysis to extract business logic from database for modernization

---

**ARGUMENTS**:

- **Optional**: Database DDL folder path relative to repository root (e.g., `./database/ddl` or `./sql-scripts`)
  - If not provided, the skill will search for common database DDL locations
- **Optional**: Specific domain name to analyze
  - If not provided, generates documentation for ALL domains identified from 02-DATA-MODEL-AND-RELATIONSHIPS.md or discovered via naming patterns
  - If provided, generates only the specified domain

**Note**: The skill will automatically locate the legacylift-docs folder and database DDL files within the repository structure.
