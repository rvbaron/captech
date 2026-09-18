---
name: data-dictionary-generator
description: Generates exhaustive, database-agnostic data dictionaries for domains. Documents EVERY table, EVERY column with logical data types, constraints, and relationships for migration to any target database platform.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Task, TodoWrite
---

# Data Dictionary Generator

This skill generates **exhaustive, database-agnostic data dictionaries** documenting every table, column, constraint, and relationship for a database domain. The documentation uses **logical data types** (string, integer, decimal, etc.) rather than database-specific SQL, making it suitable for migration to any target platform (PostgreSQL, Oracle, cloud databases, etc.).

## Instructions

The data-dictionary-generator skill systematically analyzes all database artifacts for a domain and produces complete logical data model documentation:

**12-DATA-DICTIONARY-{DOMAIN}.md** - Complete data dictionary (90-120 min read per domain)

Output files are placed directly in the `legacylift-docs/` folder.

## Examples

```
Generate data dictionary for the Legal Entities domain.
```

```
Use data-dictionary-generator on the Claims Management domain.
```

```
Create complete data dictionary for Point of Interconnection domain.
```

---

## Execution Guidelines: Persistence and Autonomy

**Your context window will be automatically compacted as it approaches its limit, allowing you to continue working indefinitely from where you left off. Therefore, do not stop tasks early due to token budget concerns.**

**Critical Requirements:**
- As you approach your token budget limit, save your current progress and state to memory before the context window refreshes
- Always be as persistent and autonomous as possible
- Complete tasks fully, even if the end of your budget is approaching
- Never artificially stop any task early regardless of the context remaining
- If context compaction occurs, resume exactly where you left off using the incremental writing pattern
- The marker `<!-- MORE CONTENT TO FOLLOW -->` enables seamless continuation after context refresh

**Handling Context Compaction:**
1. Document current table number and phase in todo list
2. Ensure marker is present in document for continuation
3. After refresh, read document to determine last completed table
4. Continue with next batch of tables
5. Maintain same format and quality standards throughout

---

## What Gets Documented

**⚠️ CRITICAL RULE #1: This is EXHAUSTIVE documentation. EVERY table must be documented. EVERY column must be documented. NO summaries. NO placeholders. If the domain has 42 tables with 687 columns total, then ALL 42 tables and ALL 687 columns must be documented with complete specifications.**

### 📊 **Every Table** (100% Coverage)
- ✅ Table name and business purpose
- ✅ Primary key columns
- ✅ Unique constraints
- ✅ Business description
- ✅ Row counts and data volumes (if available)

### 📝 **Every Column** (100% Coverage)
- ✅ Column name
- ✅ **Logical data type** (String, Integer, Decimal, Boolean, Date, DateTime, Binary, etc.)
- ✅ Length/Precision/Scale (e.g., String(50), Decimal(18,2))
- ✅ Required vs Optional (NOT NULL vs nullable)
- ✅ Default value (if any)
- ✅ Identity/Auto-increment specification
- ✅ Computed/Calculated column indicator
- ✅ **Business description** - what the column represents
- ✅ **Valid values** - enumeration, code list, or value range
- ✅ **Example values** - typical data examples
- ✅ **Business rules** - constraints, validation rules

### 🔗 **Relationships** (All Documented)
- ✅ Relationship type (one-to-many, many-to-many, one-to-one)
- ✅ Parent table and columns
- ✅ Child table and columns
- ✅ Cardinality (required vs optional)
- ✅ Cascade behavior (delete cascade, restrict, etc.)
- ✅ Business relationship description

### 📐 **Indexes** (Purpose Documented)
- ✅ Primary key index
- ✅ Foreign key indexes
- ✅ Unique indexes
- ✅ Performance indexes (with columns and purpose)

### ⚙️ **Constraints** (Business Rules)
- ✅ Primary key constraints
- ✅ Foreign key constraints
- ✅ Unique constraints
- ✅ Check constraints (business rules)
- ✅ Default value constraints

## Logical Data Type Mapping

This skill translates database-specific types to **logical data types** suitable for any platform:

| Logical Type | Description | SQL Server Example | PostgreSQL Example | Purpose |
|--------------|-------------|-------------------|-------------------|---------|
| **String** | Text data | VARCHAR, CHAR, NVARCHAR | VARCHAR, TEXT | Names, codes, descriptions |
| **Integer** | Whole numbers | INT, BIGINT, SMALLINT, TINYINT | INTEGER, BIGINT, SMALLINT | IDs, counts, codes |
| **Decimal** | Precise numbers | DECIMAL, NUMERIC, MONEY | DECIMAL, NUMERIC | Currency, measurements |
| **Float** | Approximate numbers | FLOAT, REAL | DOUBLE PRECISION, REAL | Scientific calculations |
| **Boolean** | True/False | BIT, CHAR(1) 'Y'/'N' | BOOLEAN | Flags, indicators |
| **Date** | Calendar date | DATE | DATE | Dates without time |
| **DateTime** | Date with time | DATETIME, DATETIME2, SMALLDATETIME | TIMESTAMP | Timestamps, audit dates |
| **Time** | Time of day | TIME | TIME | Time without date |
| **Binary** | Binary data | VARBINARY, IMAGE | BYTEA | Files, images, blobs |
| **GUID** | Unique identifier | UNIQUEIDENTIFIER | UUID | Global unique IDs |
| **XML** | XML documents | XML | XML | Structured documents |
| **JSON** | JSON documents | NVARCHAR (JSON) | JSON, JSONB | Semi-structured data |

**Format**: `LogicalType(length/precision,scale)`
- String(50) - varchar(50), nvarchar(50)
- Integer - int, bigint
- Decimal(18,2) - decimal(18,2), numeric(18,2)
- Boolean - bit, char(1)
- DateTime - datetime, timestamp

## Documentation Process

**⚠️ CRITICAL RULE #2: Citations are NOT a post-processing step. Every table, column, and constraint must be cited AS YOU WRITE IT. Never write specifications first and add citations later.**

The skill follows a systematic 6-phase approach:

### Phase 0: Load Fact Graph (if available)

**Objective**: Check for and load pre-generated fact graph to avoid redundant database structure analysis.

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
        print("   Falling back to direct DDL analysis")
        fact_graph_loaded = False
else:
    print("ℹ️ No fact graph found, using direct DDL analysis")

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

def find_facts_by_subject(subject_id, predicate=None):
    """Find all facts for a specific subject, optionally filtered by predicate"""
    if predicate:
        return [f for f in facts if f['subject_id'] == subject_id and f['predicate'] == predicate]
    return [f for f in facts if f['subject_id'] == subject_id]

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

**Fact-Graph Provides for Data Dictionary Generation:**
- ✅ All SQL table entities with file paths and line ranges
- ✅ All column facts (has_column) with data types
- ✅ All constraint facts (is_required, is_nullable, is_unique, is_indexed, is_primary_key)
- ✅ All foreign key relations with cardinality
- ✅ Domain classification for filtering tables by domain
- ✅ Complete evidence (file paths + line ranges) for citations

**Usage in Subsequent Phases:**
```python
if fact_graph_loaded:
    # Get all tables in a specific domain
    domain_tables = find_entities_by_domain('LegalEntities')
    # OR get all tables across all domains
    all_tables = find_entities_by_type('table')

    # For each table, get columns
    for table in domain_tables:
        table_id = table['id']
        columns = find_facts_by_subject(table_id, 'has_column')
        constraints = find_facts_by_subject(table_id, 'is_required') + \
                     find_facts_by_subject(table_id, 'is_unique') + \
                     find_facts_by_subject(table_id, 'is_primary_key')

        # Get foreign key relations
        fk_relations = [r for r in relations if r['source_id'] == table_id and r['type'] == 'foreign_key']
else:
    # Fallback to direct DDL file analysis
    # ... original grep/glob commands ...
```

### Phase 1: Domain Discovery & Inventory

**With Fact-Graph** (Preferred):
```python
if fact_graph_loaded:
    # Option 1: Filter by domain if domain classification exists
    domain_name = "LegalEntities"  # User-specified domain
    domain_tables = find_entities_by_domain(domain_name)

    # Option 2: Filter by naming pattern/prefix
    all_tables = find_entities_by_type('table')
    domain_tables = [t for t in all_tables if t['name'].startswith('LE_') or 'LegalEntity' in t['file']]

    # Option 3: All tables (if generating complete data dictionary)
    domain_tables = find_entities_by_type('table')

    print(f"📊 Domain Inventory:")
    print(f"   Total tables: {len(domain_tables)}")

    # Estimate total columns
    total_columns = 0
    for table in domain_tables:
        table_columns = find_facts_by_subject(table['id'], 'has_column')
        total_columns += len(table_columns)
        print(f"   - {table['name']}: {len(table_columns)} columns")

    print(f"\n   Total columns to document: {total_columns}")
    print(f"   All table definitions have file paths and line ranges for citations")
```

**Without Fact-Graph** (Fallback):
- Locate database DDL files (Tables, Views, Stored Procedures)
- Identify ALL tables in the domain (by prefix or naming pattern)
- Count total tables, estimate total columns
- Verify DDL file paths and accessibility
- Understand domain scope and boundaries

**⚠️ CRITICAL: Create complete inventory. If 42 tables exist, document all 42 tables. NO exceptions.**

### Phase 2: Table Structure Analysis

**With Fact-Graph** (Preferred):
```python
if fact_graph_loaded:
    # For EACH table in inventory
    for table in domain_tables:
        table_id = table['id']
        table_name = table['name']
        table_file = table['file']
        table_line_range = table['line_range']

        print(f"\nAnalyzing table: {table_name}")

        # Get ALL columns with data types
        column_facts = find_facts_by_subject(table_id, 'has_column')
        print(f"   Columns: {len(column_facts)}")

        # Extract column details
        for col_fact in column_facts:
            col_name = col_fact['object']
            col_type = col_fact.get('attributes', {}).get('data_type', 'unknown')
            col_line = col_fact['evidence'][0]['line_range'] if col_fact.get('evidence') else None

            # Translate database-specific type to logical type
            logical_type = translate_to_logical_type(col_type)
            print(f"      - {col_name}: {col_type} → {logical_type}")

        # Get constraints
        pk_facts = find_facts_by_subject(table_id, 'is_primary_key')
        required_facts = find_facts_by_subject(table_id, 'is_required')
        unique_facts = find_facts_by_subject(table_id, 'is_unique')
        indexed_facts = find_facts_by_subject(table_id, 'is_indexed')

        print(f"   Primary Keys: {len(pk_facts)}")
        print(f"   Required Columns: {len(required_facts)}")
        print(f"   Unique Constraints: {len(unique_facts)}")
        print(f"   Indexes: {len(indexed_facts)}")

        # Get foreign key relations
        fk_relations = [r for r in relations if r['source_id'] == table_id and r['type'] == 'foreign_key']
        print(f"   Foreign Keys: {len(fk_relations)}")

        # All data has file:line evidence for citations
        # Citation format: [📄](file_path:line)
```

**Data Type Translation Function**:
```python
def translate_to_logical_type(db_type):
    """Translate database-specific type to logical type"""
    db_type_lower = db_type.lower()

    # String types
    if 'varchar' in db_type_lower or 'char' in db_type_lower or 'text' in db_type_lower:
        # Extract length if present: varchar(50) → String(50)
        import re
        match = re.search(r'\((\d+)\)', db_type)
        if match:
            return f"String({match.group(1)})"
        return "String"

    # Integer types
    if db_type_lower in ['int', 'integer', 'bigint', 'smallint', 'tinyint']:
        return "Integer"

    # Decimal types
    if 'decimal' in db_type_lower or 'numeric' in db_type_lower or 'money' in db_type_lower:
        # Extract precision/scale: decimal(18,2) → Decimal(18,2)
        import re
        match = re.search(r'\((\d+),(\d+)\)', db_type)
        if match:
            return f"Decimal({match.group(1)},{match.group(2)})"
        return "Decimal"

    # Float types
    if 'float' in db_type_lower or 'real' in db_type_lower or 'double' in db_type_lower:
        return "Float"

    # Boolean types
    if 'bit' in db_type_lower or db_type_lower == 'boolean':
        return "Boolean"

    # Date/Time types
    if db_type_lower == 'date':
        return "Date"
    if 'datetime' in db_type_lower or 'timestamp' in db_type_lower:
        return "DateTime"
    if db_type_lower == 'time':
        return "Time"

    # Binary types
    if 'binary' in db_type_lower or 'image' in db_type_lower or 'bytea' in db_type_lower:
        return "Binary"

    # GUID types
    if 'uniqueidentifier' in db_type_lower or 'uuid' in db_type_lower:
        return "GUID"

    # XML/JSON types
    if 'xml' in db_type_lower:
        return "XML"
    if 'json' in db_type_lower:
        return "JSON"

    # Default fallback
    return f"String (from {db_type})"
```

**Without Fact-Graph** (Fallback):
- For EACH table (all tables, no exceptions):
  - Read DDL file completely
  - Extract table definition
  - Extract ALL column definitions with data types
  - **Translate** database-specific types to logical types
  - Extract ALL constraints (PK, FK, CHECK, UNIQUE, DEFAULT)
  - Extract indexes
  - Identify relationships to other tables
  - Extract business rules from check constraints

**⚠️ CRITICAL: This is NOT sampling. Read EVERY table DDL file. Extract EVERY column. Translate EVERY data type to logical equivalent.**

### Phase 3: Relationship Mapping

**With Fact-Graph** (Preferred):
```python
if fact_graph_loaded:
    # Get all foreign key relations
    all_fk_relations = find_relations_by_type('foreign_key')

    # Filter for domain tables only
    domain_table_ids = {t['id'] for t in domain_tables}
    domain_fk_relations = [r for r in all_fk_relations
                           if r['source_id'] in domain_table_ids or r['target_id'] in domain_table_ids]

    print(f"\n📊 Relationship Analysis:")
    print(f"   Total foreign key relationships: {len(domain_fk_relations)}")

    # Build relationship map
    relationships = []
    for fk_rel in domain_fk_relations:
        source_table = get_entity_by_id(fk_rel['source_id'])
        target_table = get_entity_by_id(fk_rel['target_id'])

        # Get cardinality from fact or relation attributes
        cardinality_facts = find_facts_by_subject(fk_rel['id'], 'has_cardinality')
        cardinality = cardinality_facts[0]['object'] if cardinality_facts else 'many-to-one'

        # Get columns involved
        source_column = fk_rel.get('attributes', {}).get('source_column')
        target_column = fk_rel.get('attributes', {}).get('target_column')

        # Get cascade behavior
        cascade_delete = fk_rel.get('attributes', {}).get('cascade_delete', False)
        cascade_update = fk_rel.get('attributes', {}).get('cascade_update', False)

        relationship = {
            'source_table': source_table['name'],
            'target_table': target_table['name'],
            'source_column': source_column,
            'target_column': target_column,
            'cardinality': cardinality,
            'cascade_delete': cascade_delete,
            'cascade_update': cascade_update,
            'evidence': fk_rel.get('evidence', [])
        }
        relationships.append(relationship)

        print(f"   {source_table['name']}.{source_column} → {target_table['name']}.{target_column} ({cardinality})")

    # Identify junction tables (many-to-many)
    junction_tables = []
    for table in domain_tables:
        table_id = table['id']
        # Junction tables typically have 2+ foreign keys and few other columns
        table_fks = [r for r in domain_fk_relations if r['source_id'] == table_id]
        table_columns = find_facts_by_subject(table_id, 'has_column')

        if len(table_fks) >= 2 and len(table_columns) <= len(table_fks) + 2:
            junction_tables.append({
                'table': table['name'],
                'foreign_keys': len(table_fks),
                'total_columns': len(table_columns)
            })

    if junction_tables:
        print(f"\n   Identified junction tables: {len(junction_tables)}")
        for jt in junction_tables:
            print(f"      - {jt['table']}: {jt['foreign_keys']} FKs, {jt['total_columns']} columns")

    # Identify parent-child hierarchies (self-referencing)
    hierarchies = []
    for fk_rel in domain_fk_relations:
        if fk_rel['source_id'] == fk_rel['target_id']:
            table = get_entity_by_id(fk_rel['source_id'])
            hierarchies.append({
                'table': table['name'],
                'column': fk_rel.get('attributes', {}).get('source_column')
            })

    if hierarchies:
        print(f"\n   Identified hierarchies (self-referencing): {len(hierarchies)}")
        for h in hierarchies:
            print(f"      - {h['table']}.{h['column']} (parent reference)")
```

**Without Fact-Graph** (Fallback):
- Map ALL foreign key relationships
- Identify junction tables for many-to-many
- Document parent-child hierarchies
- Map cross-domain references
- Determine cardinality (required/optional)
- Document cascade behaviors

### Phase 4: Document Generation with Inline Citations

**CRITICAL: Write incrementally with inline citations. Use marker replacement pattern for long documents.**

**Citation Generation with Fact-Graph**:
```python
if fact_graph_loaded:
    # Citations come from evidence fields
    for table in domain_tables:
        # Table citation
        table_file = table['file']
        table_line_start = table['line_range'][0]
        table_citation = f"[📄]({table_file}:{table_line_start})"

        # Column citations
        column_facts = find_facts_by_subject(table['id'], 'has_column')
        for col_fact in column_facts:
            col_name = col_fact['object']
            col_evidence = col_fact.get('evidence', [])
            if col_evidence:
                col_file = col_evidence[0]['file']
                col_line = col_evidence[0]['line_range'][0]
                col_citation = f"[📄]({col_file}:{col_line})"

        # Constraint citations
        pk_facts = find_facts_by_subject(table['id'], 'is_primary_key')
        for pk_fact in pk_facts:
            pk_evidence = pk_fact.get('evidence', [])
            if pk_evidence:
                pk_citation = f"[📄]({pk_evidence[0]['file']}:{pk_evidence[0]['line_range'][0]})"

        # Foreign key citations
        fk_relations = [r for r in relations if r['source_id'] == table['id'] and r['type'] == 'foreign_key']
        for fk_rel in fk_relations:
            fk_evidence = fk_rel.get('evidence', [])
            if fk_evidence:
                fk_citation = f"[📄]({fk_evidence[0]['file']}:{fk_evidence[0]['line_range'][0]})"
```

**Example Table Documentation with Fact-Graph Citations**:
```markdown
## Table: Orders [📄](src/database/tables/Orders.sql:1)

**Purpose**: Stores customer order information including order details, status, and fulfillment data.

| Column | Type | Required | Description | Valid Values | Constraints | Citation |
|--------|------|----------|-------------|--------------|-------------|----------|
| OrderID | Integer | Yes | Unique order identifier | Auto-increment | Primary Key, Identity | [📄](src/database/tables/Orders.sql:3) |
| CustomerID | Integer | Yes | Reference to customer | Valid customer ID | Foreign Key → Customers.CustomerID | [📄](src/database/tables/Orders.sql:4) |
| OrderDate | DateTime | Yes | Date order was placed | Valid datetime | Default: GETDATE() | [📄](src/database/tables/Orders.sql:5) |
| TotalAmount | Decimal(18,2) | Yes | Total order amount | >= 0 | Check: TotalAmount >= 0 | [📄](src/database/tables/Orders.sql:6) |
| Status | String(20) | Yes | Order status | 'Pending', 'Approved', 'Shipped', 'Cancelled' | Check constraint | [📄](src/database/tables/Orders.sql:7) |
| ShippingAddress | String(200) | No | Delivery address | Valid address | Nullable | [📄](src/database/tables/Orders.sql:8) |

**Relationships**:
- **Many-to-One**: Orders → Customers (via CustomerID) [📄](src/database/tables/Orders.sql:15)
  - Cardinality: Many orders per customer
  - Cascade: No cascade delete (preserve order history)

**Indexes**:
- Primary Key: PK_Orders (OrderID) [📄](src/database/tables/Orders.sql:3)
- Foreign Key Index: IX_Orders_CustomerID (CustomerID) [📄](src/database/tables/Orders.sql:16)
- Performance Index: IX_Orders_OrderDate (OrderDate DESC) [📄](src/database/tables/Orders.sql:17)
```

#### Incremental Writing Workflow:

**Initial Document Setup**:
1. Write front matter (title, scope, TOC)
2. Write domain overview and statistics
3. Write first 5-10 tables with COMPLETE specifications
4. Add marker: `<!-- MORE CONTENT TO FOLLOW -->`

**For Each Additional Batch**:
1. **Gather DDL FIRST**: Read table DDL files for next 5-10 tables
2. **Extract ALL details**: Columns, types, constraints, relationships
3. **Translate data types**: Convert to logical types
4. **Write WITH citations**: Document tables with inline DDL citations
5. **Replace marker**: Edit tool replaces `<!-- MORE CONTENT TO FOLLOW -->` with new content + marker
6. **Repeat**: Continue until ALL tables documented

**Final Section**:
1. Write relationship summary section
2. Write cross-domain integration section
3. Write data volume statistics
4. Remove marker (no more content to follow)

#### Citation-First Writing Pattern:

```
For each table:
  a) Read table DDL file NOW [📄](path/table.sql:line)
  b) Extract ALL columns with database-specific types
  c) Translate to logical types (VARCHAR(50) → String(50))
  d) Write table header WITH citation
  e) Write EVERY column WITH:
     - Logical data type
     - Required/Optional
     - Description (business meaning)
     - Valid values or examples
     - Citation to DDL column definition
  f) Write EVERY constraint WITH citation
  g) Write relationships WITH cardinality and citations
  h) Move to next table
```

**⚠️ NEVER write a column without logical data type.**
**⚠️ NEVER write "String" without length (String(50)).**
**⚠️ NEVER write "Decimal" without precision (Decimal(18,2)).**
**⚠️ NEVER write a constraint without its business rule.**
**⚠️ NEVER write ANY database object without a citation.**

### Phase 5: Validation & Completeness Check
- Verify ALL tables from inventory are documented
- Verify EVERY column has logical data type
- Verify EVERY column has Required/Optional specification
- Verify ALL foreign keys are documented
- Verify ALL constraints are documented as business rules
- Check for missing citations
- Validate cross-references

**⚠️ CRITICAL: Before completing, count documented tables vs. inventory. If inventory has 42 tables but only 35 documented, you're NOT done. Document the remaining 7 tables.**

---

## Incremental Document Writing Process

**⚠️ MANDATORY: All data dictionaries must be written incrementally to manage context and avoid token limits.**

### Writing Pattern

#### 1. Initial Document (300-500 lines)
```markdown
# Data Dictionary: {DOMAIN} Domain
[Front matter, TOC, overview, statistics]

## Table: TableName1
**Purpose**: Business description

| Column | Type | Required | Description | Valid Values | Constraints |
|--------|------|----------|-------------|--------------|-------------|
| columnName | String(50) | Yes | Business meaning | Examples | PK, FK, etc |
[ALL columns for table 1]

**Relationships**: ...

## Table: TableName2
[Complete specification with ALL columns]

[... continue for first 5-10 tables ...]

<!-- MORE CONTENT TO FOLLOW -->
```

#### 2. Each Additional Batch (5-10 tables)
```
Use Edit tool:
- old_string: <!-- MORE CONTENT TO FOLLOW -->
- new_string:
  ## Table: TableName11
  [Complete specification with ALL columns]

  ## Table: TableName12
  [Complete specification with ALL columns]

  [... 5-10 more tables ...]

  <!-- MORE CONTENT TO FOLLOW -->
```

#### 3. Final Section
```
Use Edit tool:
- old_string: <!-- MORE CONTENT TO FOLLOW -->
- new_string:
  [Last few tables with ALL columns]

  ## Relationship Summary
  [All cross-table relationships]

  ## Cross-Domain Integration
  [Integration points]

  ---
  *Generated By LegacyLift AI by CapTech*
```

---

## Key Differences from database-layer-documenter

| Aspect | database-layer-documenter | data-dictionary-generator |
|--------|---------------------------|---------------------------|
| **Purpose** | Modernization planning | Complete technical reference |
| **Scope** | Key tables & business logic | EVERY table, EVERY column |
| **Data Types** | Database-specific (VARCHAR, INT) | **Logical (String, Integer)** |
| **SQL Syntax** | Includes CREATE TABLE statements | **NO SQL - logical specs only** |
| **Depth** | Important columns | ALL columns with full specs |
| **Format** | Narrative description | Structured table format |
| **Focus** | Business logic extraction | **Field-level data model** |
| **Completeness** | Selective (15-20 key tables) | **EXHAUSTIVE (ALL tables)** |
| **Platform** | Database-specific | **Database-agnostic** |

## Output Quality Standards

All generated data dictionaries include:

✅ **100% Table Coverage** - Every table in domain documented
✅ **100% Column Coverage** - Every column with logical type, required/optional, description
✅ **Logical Data Types** - Database-agnostic types (String, Integer, Decimal, etc.)
✅ **No SQL Syntax** - Pure data model specifications
✅ **Complete Constraints** - All PK, FK, UNIQUE as business rules
✅ **Relationship Documentation** - All FKs with cardinality and cascade rules
✅ **Inline Citations** - Every specification cited with DDL file:line
✅ **Business Descriptions** - Every column explains business meaning
✅ **Value Domains** - Valid values, ranges, or examples where applicable
✅ **Structured Format** - Tables for easy reference and parsing

## Success Criteria

Data dictionary is considered complete when:

✅ **ALL tables documented** - Table count in doc = table count in domain inventory
✅ **ALL columns documented** - Every column has logical type, required/optional, description
✅ **NO SQL syntax** - Only logical data model specifications
✅ **ALL constraints as business rules** - Every constraint explained in business terms
✅ **ALL relationships mapped** - Every foreign key with cardinality
✅ **ALL citations present** - Every table/column/constraint has DDL citation
✅ **No placeholders** - No "Additional tables...", "Other columns...", "Etc."
✅ **No summaries** - No "Tables 1-10 follow similar pattern"
✅ **Cross-references valid** - All FK references resolve to documented tables

## Skill Execution

When this skill is invoked, I will:

1. **Clarify the Scope**
   - Domain name (e.g., "Legal Entities", "Point of Interconnection")
   - Database DDL location
   - Output location (legacylift-docs/)

2. **Perform Domain Discovery**
   - Find all table DDL files for domain
   - Count tables, estimate columns
   - Create inventory of all tables

3. **Create Todo List**
   - Phase 0: Load Fact Graph (if available)
   - Phase 1: Domain Discovery & Inventory
   - Phase 2: Analyze ALL table structures
   - Phase 3: Map ALL relationships
   - Phase 4: Write front matter + first 10 tables
   - Phase 5-N: Write remaining tables in batches
   - Phase N+1: Write final sections & validation
   - Phase N+2: Completeness check

4. **Execute Incremental Writing**
   - Write initial document with first batch
   - Add marker: `<!-- MORE CONTENT TO FOLLOW -->`
   - For each batch:
     * Read DDL for next 5-10 tables
     * Translate types to logical types
     * Use Edit to replace marker with new tables + marker
   - Final batch: Replace marker with last tables + closing

5. **Validate Completeness**
   - Count documented tables vs. inventory
   - Verify all columns have logical types
   - Verify no SQL syntax present
   - Check for missing citations

6. **Deliver Complete Data Dictionary**
   - File: 12-DATA-DICTIONARY-{DOMAIN}.md
   - 100% coverage guaranteed
   - Database-agnostic specifications
   - Ready for migration to any platform

---

**⚠️ FINAL REMINDER: This skill generates EXHAUSTIVE, database-agnostic documentation using logical data types. If you identify 47 tables, you MUST document all 47 tables with EVERY column as String/Integer/Decimal/etc. NO SQL syntax. NO summaries. NO placeholders. Complete logical data model specifications only.**