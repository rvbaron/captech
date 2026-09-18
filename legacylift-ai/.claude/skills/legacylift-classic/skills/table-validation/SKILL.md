---
name: table-validation
description: Validates ORM mappings (Hibernate, NHibernate, Entity Framework) against SQL DDL to ensure data model integrity. Generates executive summary and detailed discrepancy reports for database migration planning.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, BashOutput, Task, TodoWrite, Skill, WebFetch
---

# Table Validation Documenter

This skill performs **comprehensive validation** of Object-Relational Mapping (ORM) frameworks against SQL DDL schema definitions to assess data model integrity, identify discrepancies, and support database migration planning.

## Instructions

The table-validation skill systematically compares SQL DDL table definitions with ORM mapping files (Hibernate, NHibernate, Entity Framework) and produces documentation files based on the presence of an ORM:

**If ORM detected (Hibernate, NHibernate, Entity Framework):**
1. **06-TABLE-VALIDATION-EXECUTIVE-SUMMARY.md** - High-level assessment (10-15 min read)
2. **06-TABLE-VALIDATION-COMPREHENSIVE-REPORT.md** - Detailed table-by-table analysis (45-60 min read)
3. **06-TABLE-VALIDATION-DISCREPANCIES.md** - Explanation of intentional design patterns vs real issues (20-30 min read)

**If NO ORM detected:**
1. **06-TABLE-VALIDATION-EXECUTIVE-SUMMARY.md** - High-level assessment of SQL schema only (10-15 min read)

Output files are placed in the **target repository's** `legacylift-docs/` folder within the repository being analyzed.

## Examples

```
Use the table-validation skill on this repository.
```

```
Validate ORM mappings with table-validation.
```

```
Generate table validation reports for migration planning.
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

This skill provides **exhaustive validation** of:

### 📊 **SQL DDL Schema**
- ✅ ALL tables with complete column definitions
- ✅ Primary keys, foreign keys, unique constraints
- ✅ Check constraints and default values
- ✅ Data types, nullability, identity columns
- ✅ Table-level constraints and business rules

### 🔗 **ORM Mapping Files** (Hibernate, NHibernate, Entity Framework)
- ✅ Entity class definitions or XML mapping files
- ✅ Property mappings to database columns
- ✅ Relationship mappings (one-to-many, many-to-one, many-to-many)
- ✅ Primary key generators and identity strategies
- ✅ Custom type converters and user types
- ✅ Cascade rules and fetch strategies
- ✅ Lazy loading configuration

### ✅ **Validation Checks**
- ✅ **Column Coverage:** Every SQL column mapped in ORM (or documented as intentionally unmapped)
- ✅ **Type Mappings:** SQL types correctly mapped to ORM types (or custom converters documented)
- ✅ **Relationship Integrity:** All foreign keys represented as ORM associations
- ✅ **Constraint Validation:** Primary keys, unique constraints, NOT NULL consistency
- ✅ **Bidirectional Relationships:** Parent-child properly configured both ways
- ✅ **Naming Conventions:** Property names vs column names (documented differences)
- ✅ **Unmapped Tables:** Tables without ORM mappings (categorized by intent: Quartz, ETL, temp, etc.)

### 🔍 **Pattern Analysis**
- ✅ Audit trail patterns (createDate, updateDate, etc.)
- ✅ Temporal data patterns (effectiveDate, terminationDate)
- ✅ Soft delete patterns
- ✅ Optimistic locking strategies (timestamps, version columns)
- ✅ Custom type converters (Y/N flags, trimmed strings, enums)
- ✅ Circular dependency workarounds
- ✅ Legacy system integration patterns (old ID columns)

## Documentation Process

The skill follows a systematic 5-phase approach:

**⚠️ CRITICAL: Citations are NOT a post-processing step. Every claim must be cited AS YOU WRITE IT. Never write prose first and add citations later.**

### Phase 0: Load Fact Graph (if available)

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Load Fact Graph", "phase_number": 0, "total_phases": 5, "progress_percent": 0, "current_task": "Checking for fact graph", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
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
```

**Usage in Subsequent Phases:**
```python
if fact_graph_loaded:
    # Use fact graph data
    sql_tables = find_entities_by_type('table')
    orm_entities = [e for e in entities if e['type'] in ['model', 'class'] and 'Table' in str(e.get('attributes', {}).get('annotations', []))]

    # Get columns for each table
    for table in sql_tables:
        table_id = table['id']
        columns = [f for f in facts if f['subject_id'] == table_id and f['predicate'] == 'has_column']
else:
    # Fallback to direct code analysis
    # ... original DDL parsing and grep commands ...
```

### Phase 1: ORM Detection (Technology Discovery)

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "ORM Detection", "phase_number": 1, "total_phases": 5, "progress_percent": 20, "current_task": "Detecting ORM framework", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

- Detect if project uses an ORM framework:
  - **Hibernate:** Look for .hbm.xml files, hibernate.cfg.xml, @Entity annotations
  - **NHibernate:** Look for .hbm.xml files, NHibernate.dll references, FluentNHibernate
  - **Entity Framework:** Look for DbContext classes, .edmx files, DbSet properties, EF Core references
- Identify SQL DDL location (database project, migration scripts, schema files)
- Determine validation scope (full comparison if ORM detected, schema-only if not)

### Phase 2: SQL DDL Analysis (Schema Inventory)

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "SQL DDL Analysis", "phase_number": 2, "total_phases": 5, "progress_percent": 40, "current_task": "Analyzing SQL DDL schemas", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

For **EVERY table in SQL DDL**:
- Extract complete DDL with all columns
- Document all constraints (PK, FK, unique, check, default)
- Identify relationships to other tables (foreign keys)
- Map data types and nullability rules
- Document indexes on the table
- Create table inventory for comparison

**Fact-Graph Integration:**
```python
if fact_graph_loaded:
    # Use fact-graph for SQL table discovery
    sql_tables = find_entities_by_type('table')

    for table in sql_tables:
        table_id = table['id']
        table_name = table['name']
        table_file = table['file']
        table_line_range = table['line_range']

        # Get all columns for this table
        column_facts = [f for f in facts if f['subject_id'] == table_id and f['predicate'] == 'has_column']

        # Get constraints for this table
        required_facts = [f for f in facts if f['subject_id'] == table_id and f['predicate'] == 'is_required']
        nullable_facts = [f for f in facts if f['subject_id'] == table_id and f['predicate'] == 'is_nullable']
        unique_facts = [f for f in facts if f['subject_id'] == table_id and f['predicate'] == 'is_unique']
        indexed_facts = [f for f in facts if f['subject_id'] == table_id and f['predicate'] == 'is_indexed']

        # Get primary key facts
        pk_facts = [f for f in facts if f['subject_id'] == table_id and f['predicate'] == 'has_primary_key']

        # Get foreign key relations
        fk_relations = [r for r in relations if r['source_id'] == table_id and r['type'] == 'foreign_key']

        # Citations available from evidence
        citation = f"[📄]({table_file}:{table_line_range[0]})"
else:
    # Fallback: Parse SQL DDL files directly
    # Search for DDL files (*.sql, create_tables.sql, schema.sql, etc.)
    # Parse each DDL file to extract table definitions
    # Use Grep/Read tools to find CREATE TABLE statements
```

### Phase 3: ORM Mapping Analysis (If ORM Detected)

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "ORM Mapping Analysis", "phase_number": 3, "total_phases": 5, "progress_percent": 60, "current_task": "Analyzing ORM mappings", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

For **EVERY ORM mapping** (entity class, .hbm.xml file, DbContext):
- Identify mapped table name
- Extract all property-to-column mappings
- Document relationship mappings (many-to-one, one-to-many, one-to-one)
- Identify primary key generators
- Document custom type converters
- Note cascade rules and fetch strategies
- Create ORM inventory for comparison

**Fact-Graph Integration:**
```python
if fact_graph_loaded:
    # Use fact-graph for ORM entity discovery
    # Find entities with ORM annotations (Entity Framework, Hibernate, NHibernate)
    orm_entities = [e for e in entities if e['type'] in ['model', 'class']]

    # Filter for entities with ORM annotations
    orm_mapped_entities = []
    for entity in orm_entities:
        annotations = entity.get('attributes', {}).get('annotations', [])
        # Check for EF annotations: [Table], DbContext.DbSet<T>
        # Check for Hibernate/NHibernate annotations: @Entity, @Table, .hbm.xml mappings
        if any(annotation in str(annotations) for annotation in ['Table', 'Entity', 'Mapped']):
            orm_mapped_entities.append(entity)

    for orm_entity in orm_mapped_entities:
        entity_id = orm_entity['id']
        entity_name = orm_entity['name']
        entity_file = orm_entity['file']
        entity_line_range = orm_entity['line_range']

        # Get mapped table name from annotations or attributes
        table_name = orm_entity.get('attributes', {}).get('table_name', entity_name)

        # Get all properties for this entity
        property_facts = [f for f in facts if f['subject_id'] == entity_id and f['predicate'] == 'has_property']

        # Get column mappings (property name → column name)
        for prop in property_facts:
            prop_name = prop['object']
            data_type = prop.get('attributes', {}).get('data_type')
            column_name = prop.get('attributes', {}).get('column_name', prop_name)  # May differ from property name

        # Get relationship mappings
        one_to_many_relations = [r for r in relations if r['source_id'] == entity_id and r['type'] == 'one_to_many']
        many_to_one_relations = [r for r in relations if r['source_id'] == entity_id and r['type'] == 'many_to_one']
        one_to_one_relations = [r for r in relations if r['source_id'] == entity_id and r['type'] == 'one_to_one']

        # Get constraint information
        required_props = [f for f in facts if f['subject_id'] == entity_id and f['predicate'] == 'is_required']
        unique_props = [f for f in facts if f['subject_id'] == entity_id and f['predicate'] == 'is_unique']

        # Citations available from evidence
        citation = f"[📄]({entity_file}:{entity_line_range[0]})"
else:
    # Fallback: Search for ORM entity classes and mapping files directly
    # For Entity Framework: Grep for DbContext, DbSet<T>, [Table], [Column] attributes
    # For Hibernate: Grep for @Entity, @Table, .hbm.xml files
    # For NHibernate: Grep for .hbm.xml, FluentNHibernate mappings
    # Use Grep/Read tools to extract entity definitions
```

### Phase 4: Comparison & Validation (Discrepancy Detection)

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Comparison & Validation", "phase_number": 4, "total_phases": 5, "progress_percent": 80, "current_task": "Validating ORM against DDL", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

- **Table Coverage:** All SQL tables have corresponding ORM mappings?
  - If not, categorize unmapped tables (Quartz, integration, temporary, specialized)
- **Column Coverage:** All SQL columns mapped in ORM?
  - If not, identify missing columns or intentional omissions
- **Type Consistency:** SQL types match ORM types (or custom converters explained)?
- **Relationship Integrity:** All foreign keys represented as ORM associations?
- **Constraint Validation:** Primary keys, unique constraints, NOT NULL consistency?
- **Bidirectional Relationships:** Parent-child properly configured?
- **Property Name Differences:** Document where property names differ from column names
- **Circular Dependencies:** Identify workarounds for circular references

### Phase 5: Document Generation with Inline Citations

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Document Generation", "phase_number": 5, "total_phases": 5, "progress_percent": 95, "current_task": "Generating validation reports", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

**CRITICAL: Write WITH citations from the start, not added later.**

For each document:
1. **Plan**: Outline what to document based on validation results
2. **Search**: Find ALL relevant DDL files and ORM mapping files
3. **Write**: Compose WITH inline citations as you write
4. **Validate**: Every table, column, mapping, discrepancy has citations

**Citation Standards**:
- SQL table definitions → cite DDL file with line number
- ORM mappings → cite entity class or .hbm.xml file with line number
- Column mappings → cite property definition or XML mapping
- Relationship mappings → cite many-to-one/one-to-many definitions
- Discrepancies → cite both SQL DDL and ORM mapping for comparison
- Unmapped tables → cite SQL DDL only
- Custom types → cite UserType class or converter implementation

All documentation includes:
- **Comprehensive validation results** - Every table validated
- **Inline citations** - Every claim backed by DDL or ORM file reference
- **Categorized discrepancies** - Intentional patterns vs real issues
- **Migration insights** - Patterns for modernization
- **Audience-appropriate detail** - Executive summary vs comprehensive report

## Key Features

### 🎯 **ORM Framework Support**
Supports validation of:
- **Hibernate (Java):** .hbm.xml files, @Entity annotations, JPA mappings
- **NHibernate (.NET):** .hbm.xml files, FluentNHibernate, mapping conventions
- **Entity Framework (.NET):** DbContext classes, .edmx files, Code First, Database First, Fluent API

### 📊 **Comprehensive Validation**
- **100% table coverage** - Every SQL table validated
- **Column-level validation** - Every column checked for mapping
- **Relationship validation** - All foreign keys verified
- **Type mapping validation** - SQL types vs ORM types
- **Constraint validation** - Primary keys, unique constraints, NOT NULL

### 🔍 **Pattern Recognition**
Identifies common ORM patterns:
- Audit trail patterns (createUserId, createDate, updateUserId, updateDate)
- Temporal data patterns (effectiveDate, terminationDate, startDate, endDate)
- Optimistic locking (timestamp columns, version fields)
- Custom type converters (Y/N to boolean, trimmed strings, enums)
- Circular dependency workarounds (scalar properties instead of associations)
- Legacy system integration (old ID columns for migration)

### 💡 **Discrepancy Categorization**
- **✅ Intentional Design Patterns:** Custom types, property name differences, optimistic locking
- **⚠️ Minor Issues:** Nullable vs NOT NULL inconsistencies (DB enforces)
- **❌ Real Issues:** Missing mappings, broken relationships, type mismatches

### 🏗️ **Migration Readiness Assessment** (Executive Summary Only)
- Entity boundary analysis
- Relationship completeness
- Pattern consistency
- Modernization opportunities

## Output Quality Standards

All generated documentation includes:

✅ **Complete Coverage** - Every database table validated
✅ **Inline Citations** - Every table/mapping cited with DDL or ORM file and line number
✅ **Categorized Results** - Tables with mappings, tables without mappings (categorized)
✅ **Discrepancy Analysis** - Intentional patterns vs real issues
✅ **Pattern Documentation** - Common ORM patterns identified and explained
✅ **Migration Insights** - Readiness assessment for modernization
✅ **Cross-References** - Links between SQL DDL and ORM mappings
✅ **Statistics** - Object counts, coverage metrics
✅ **Audience-Appropriate Detail** - Executive summary for stakeholders, comprehensive report for engineers

## Document Structure

### 06-TABLE-VALIDATION-EXECUTIVE-SUMMARY.md (Always Generated)
High-level assessment suitable for all stakeholders:
- Overall assessment (grade: A+, A, B, C, D, F)
- Summary statistics (table counts, coverage percentages)
- Core entity validation results
- Key findings (column coverage, relationship integrity, constraints)
- Data model discrepancies (high-level)
- Architecture patterns observed
- Significant observations (strengths, smart design decisions)
- Technical debt assessment
- Conclusion with migration risk assessment

**NOTE:** Does NOT include "Migration Readiness Assessment" or "Recommendations" sections - these are saved for later phases.

### 06-TABLE-VALIDATION-COMPREHENSIVE-REPORT.md (Generated Only If ORM Detected)
Detailed table-by-table validation:
- Executive summary (brief)
- Core entities analysis (detailed, per entity)
  - SQL table structure
  - ORM mapping structure
  - Column-by-column validation table
  - Relationship validation
- Lookup/type tables analysis
- Tables without ORM mappings (categorized: Quartz, integration, temporary, specialized)
- ORM mappings without SQL tables (views, external, deprecated)
- Type mapping patterns (custom types, numeric types, etc.)
- Relationship patterns (parent-child, bidirectional, etc.)
- Constraint validation (PK, FK, unique, NOT NULL)
- Significant findings (audit trail, legacy integration, soft delete, circular dependencies, optimistic locking)
- Data model health assessment
- Appendix with file locations

### 06-TABLE-VALIDATION-DISCREPANCIES.md (Generated Only If ORM Detected)
Explanation of apparent discrepancies:
- Overview (what are "discrepancies"?)
- Categories of discrepancies
  - Custom type mappings (TrimmedString, YesNoFlag, etc.) - BY DESIGN ✅
  - Property name differences (effectiveDate → startDate) - INTENTIONAL ℹ️
  - Timestamp vs property (optimistic locking) - BY DESIGN ✅
  - Foreign keys as many-to-one (standard ORM) - BY DESIGN ✅
  - Circular dependency workarounds (smart design) - BY DESIGN ✅
- Non-issues explained (why automated tools flag false positives)
- Tables without mappings (by design: Quartz, integration, temp, specialized)
- ORM mappings without tables (views, external, configuration)
- Custom UserType details
- Validation checklist (how to review a "discrepancy")
- Real issues vs non-issues
- Conclusion (data model health)
- Reference: common patterns

## LARGE OUTPUT PAGINATION POLICY

When generating documentation or any file that may exceed output limits, you MUST paginate.

**Paging rules:**
- Write in PARTS of ~150–250 lines (never exceed ~250 lines in a single response).
- If the requested output would be larger, stop cleanly at a logical boundary (end of a subsection if possible).
- End every part with a continuation marker in this exact format:

```
<<CONTINUE file="PATH" section="SECTION_ID" part=N next="FIRST_WORDS_OF_NEXT_PARAGRAPH">>
```

**Continuation rules:**
- When the user provides a CONTINUE marker, resume exactly where you left off.
- Do NOT repeat the previous content (avoid repeating the last ~20 lines).
- Keep headings, numbering, anchors, and terminology consistent across parts.
- Do not add summaries or meta commentary unless explicitly asked.

**If writing to files is available:**
- Append new content to the target file (or insert immediately before `<!-- APPEND_POINT -->` if present).
- Never rewrite existing content unless explicitly requested.

**For large docs:**
1. First output ONLY a Table of Contents with stable SECTION_IDs and target filenames.
2. Then generate one SECTION_ID per part sequence, paging as needed.
Do not generate multiple sections in a single part unless explicitly instructed.

## Success Criteria

Documentation is considered complete when:

✅ **ORM detection performed** - Hibernate, NHibernate, or Entity Framework identified (or absence confirmed)
✅ **Every SQL table validated** - All tables checked for ORM mappings
✅ **Every ORM mapping validated** - All mappings checked against SQL DDL
✅ **Coverage metrics calculated** - Table counts, column counts, mapping percentages
✅ **Discrepancies categorized** - Intentional patterns vs real issues
✅ **Patterns identified** - Audit trail, temporal data, custom types, etc.
✅ **All citations present** - DDL files and ORM files with line numbers
✅ **Executive summary generated** - High-level assessment for all stakeholders
✅ **Comprehensive report generated** (if ORM detected) - Detailed validation results
✅ **Discrepancies guide generated** (if ORM detected) - Explanation of design patterns
✅ **Migration insights provided** - Readiness assessment for modernization

## Skill Execution

When this skill is invoked, I will:

1. **Clarify the Scope** (if needed)
   - Database DDL folder location
   - ORM framework used (or auto-detect)
   - ORM mapping files location
   - Specific tables to focus on (or ALL tables)
   - Confirm output location (target repository's legacylift-docs/ folder)

2. **Detect ORM Framework**
   - Search for Hibernate files (.hbm.xml, hibernate.cfg.xml, @Entity)
   - Search for NHibernate files (.hbm.xml, NHibernate.dll, FluentNHibernate)
   - Search for Entity Framework files (DbContext, .edmx, EF Core)
   - If ORM detected, proceed with full validation
   - If NO ORM detected, generate executive summary only (schema-only assessment)

   **⚠️ IMPORTANT: Helper Scripts Location**
   - If you need to create helper Python scripts during analysis (e.g., inventory builders, parsers), write them to: `legacylift-docs/scripts/`
   - NEVER write helper scripts to the repository root
   - Ensure the scripts directory exists before writing: `mkdir -p legacylift-docs/scripts`
   - Examples: `legacylift-docs/scripts/build_table_inventory.py`, `legacylift-docs/scripts/parse_orm_mappings.py`

3. **Create Todo List**
   - Phase 0: Load Fact Graph (if available)
   - Phase 1: ORM Detection & Technology Discovery
   - Phase 2: SQL DDL Analysis (table inventory)
   - Phase 3: ORM Mapping Analysis (if ORM detected)
   - Phase 4: Comparison & Validation (discrepancy detection)
   - Phase 5: Document Generation with Citations
     * Generate 06-TABLE-VALIDATION-EXECUTIVE-SUMMARY.md (always)
     * Generate 06-TABLE-VALIDATION-COMPREHENSIVE-REPORT.md (if ORM detected)
     * Generate 06-TABLE-VALIDATION-DISCREPANCIES.md (if ORM detected)
   - Phase 6: Review & Validation

4. **Execute Validation Process**
   - Analyze SQL DDL for all tables
   - Analyze ORM mappings (if detected)
   - Compare table by table
   - Validate column coverage
   - Validate type mappings
   - Validate relationship integrity
   - Validate constraints
   - Categorize unmapped tables
   - Identify patterns

5. **Deliver Documentation Files**
   - **06-TABLE-VALIDATION-EXECUTIVE-SUMMARY.md** (always generated)
   - **06-TABLE-VALIDATION-COMPREHENSIVE-REPORT.md** (only if ORM detected)
   - **06-TABLE-VALIDATION-DISCREPANCIES.md** (only if ORM detected)
   - Placed in target repository's legacylift-docs/ folder
   - With comprehensive citations
   - Following template structures

6. **Provide Summary**
   - ORM framework detected (or not)
   - Total tables analyzed
   - Total ORM mappings analyzed (if applicable)
   - Coverage metrics (percentage of tables mapped)
   - Key findings (validation results)
   - Discrepancies identified (categorized)
   - Migration readiness assessment

---

## Supporting Files & Templates

This skill uses supporting files in the `templates/` directory to ensure consistent, comprehensive documentation output.

### Template Structure

| Template File | Purpose | Usage |
|---------------|---------|-------|
| **[06-TABLE-VALIDATION-EXECUTIVE-SUMMARY.md](./templates/06-TABLE-VALIDATION-EXECUTIVE-SUMMARY.md)** | Structure for executive-level validation summary | Guides high-level assessment suitable for all stakeholders |
| **[06-TABLE-VALIDATION-COMPREHENSIVE-REPORT.md](./templates/06-TABLE-VALIDATION-COMPREHENSIVE-REPORT.md)** | Structure for detailed table-by-table validation | Guides comprehensive coverage of all tables and mappings (only if ORM detected) |
| **[06-TABLE-VALIDATION-DISCREPANCIES.md](./templates/06-TABLE-VALIDATION-DISCREPANCIES.md)** | Structure for discrepancy explanation guide | Guides explanation of intentional patterns vs real issues (only if ORM detected) |

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
| 06 | [TABLE-VALIDATION-*](./templates/) ⭐ | **table-validation** | ORM mapping validation reports |
| 07 | DOCUMENTATION-ACCURACY-REPORT | documentation-review | Documentation accuracy validation |
| 08 | USE-CASES-{DOMAIN} | use-case-generator | Comprehensive use case documentation |
| 09 | CITATION-VALIDATION-REPORT | citation-validator | Citation correctness validation |
| 10 | GAP-ANALYSIS-REPORT | gap-analyzer | Documentation-code gap analysis |

⭐ = Generated by this skill (creates 3 reports: EXECUTIVE-SUMMARY, COMPREHENSIVE-REPORT, and DISCREPANCIES)

### How Templates Are Used

During skill execution, I will:

1. **Reference Template**: Read the appropriate template for each document type
2. **Extract Structure**: Use the template's sections, headings, organization
3. **Fill with Validation Results**: Replace placeholders with actual validation findings
4. **Maintain Comprehensiveness**: Ensure ALL tables and mappings are covered
5. **Adapt per Project**: Customize for project-specific ORM framework and patterns
6. **Generate Conditionally**: Only generate comprehensive report and discrepancies guide if ORM detected

### Template Features

The templates include:

- **Instructional Comments**: HTML comments guiding complete coverage
- **Placeholder Syntax**: `{PLACEHOLDER}` markers for project-specific values
- **Section Organization**: Pre-structured for exhaustive documentation
- **Table Templates**: Structures for validation results and comparison matrices
- **Citation Patterns**: Examples for DDL file and ORM file references
- **Completeness Checklists**: Ensure no tables or mappings are missed
- **Conditional Content Markers**: Sections that only apply if ORM detected

---

**ARGUMENTS**:

- **Optional**: Database DDL folder path relative to repository root (e.g., `./database/ddl` or `./sql-scripts`)
  - If not provided, the skill will search for common database DDL locations
- **Optional**: ORM framework name (`hibernate`, `nhibernate`, `entity-framework`)
  - If not provided, the skill will auto-detect based on file patterns
- **Optional**: ORM mapping files folder path (e.g., `./src/mappings` or `./config/hbm`)
  - If not provided, the skill will search for common ORM mapping locations

**Note**: The skill will automatically create or use the target repository's `legacylift-docs/` folder and locate database/ORM files within the repository structure being analyzed.
