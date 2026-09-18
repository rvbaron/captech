---
name: fact-graph
description: Analyzes a codebase and generates a structured knowledge graph as JSON (entities, relations, facts) with evidence. Creates a single source of truth that other skills can consume to avoid redundant code analysis.
allowed-tools: Read, Write, Glob, Grep, Bash, Task, TodoWrite
user-invocable: true
---

# Fact Graph Generator

This skill performs systematic codebase analysis and extracts a structured knowledge graph representing entities, relationships, and verifiable facts. The output serves as a single source of truth for other documentation skills, eliminating redundant code analysis.

## Instructions

The fact-graph skill systematically analyzes your codebase using the "Skill Execution" and "Extraction Process" described below, and produces structured JSON files:

**Output Files:**
- `{repo}/legacylift-docs/context/index.json` - Master index with metadata and statistics
- `{repo}/legacylift-docs/context/packs/entities.pack.json` - All discovered entities
- `{repo}/legacylift-docs/context/packs/relations.pack.json` - All discovered relations
- `{repo}/legacylift-docs/context/packs/facts.pack.json` - All verifiable facts with evidence

## Examples

```
Use the fact-graph skill on this repository.
```

```
Generate a fact graph for the current codebase with fact-graph.
```

```
/legacylift-classic:fact-graph output_dir=repos/my_project/legacylift-docs
```

---

## Execution Guidelines: Persistence and Autonomy

**Your context window will be automatically compacted as it approaches its limit, allowing you to continue working indefinitely from where you left off. Therefore, do not stop tasks early due to token budget concerns.**

**Critical Requirements:**
- As you approach your token budget limit, save your current progress to JSON files before the context window refreshes
- Always be as persistent and autonomous as possible
- Complete tasks fully, even if the end of your budget is approaching
- Never artificially stop any task early regardless of the context remaining
- If context compaction occurs, resume exactly where you left off
- Use incremental writing for large entity collections (write 100-500 entities at a time to pack files)

**Handling Context Compaction:**
1. Document current phase in todo list
2. Persist extracted entities/relations/facts to JSON files incrementally
3. After refresh, read todo list to determine last completed phase
4. Load partial JSON files and continue extraction
5. Maintain same format and quality standards throughout

**MANDATORY Incremental JSON Writing:**

**YOU MUST USE THIS PATTERN FOR ALL LARGE COLLECTIONS (>100 items):**

### Pattern 1: Single File with Append Mode (Recommended)

```python
# Write entities in batches to single file
batch_size = 100
total_batches = (len(entities) + batch_size - 1) // batch_size

for batch_num in range(1, total_batches + 1):
    start = (batch_num - 1) * batch_size
    end = min(start + batch_size, len(entities))
    batch = entities[start:end]

    mode = 'w' if batch_num == 1 else 'a'

    with open('entities.pack.json', mode) as f:
        if batch_num == 1:
            # Write JSON header
            f.write('{\n')
            f.write('  "schema": "https://legacylift.ai/schemas/entity.json",\n')
            f.write('  "packId": "pack:domain",\n')
            f.write('  "domain": "DomainName",\n')
            f.write('  "entities": [\n')

        # Write batch entities
        for i, entity in enumerate(batch):
            indent = '    '
            entity_json = json.dumps(entity, indent=2).replace('\n', '\n' + indent)
            f.write(indent + entity_json)

            # Add comma unless last entity in entire collection
            is_last_entity = (batch_num == total_batches and i == len(batch) - 1)
            if not is_last_entity:
                f.write(',')
            f.write('\n')

        if batch_num == total_batches:
            # Write JSON footer
            f.write('  ]\n')
            f.write('}\n')

    # Mark batch completion
    print(f"<!-- BATCH {batch_num} of {total_batches} COMPLETE -->")
    # Update TodoWrite after each batch
```

### Pattern 2: Multiple Part Files (Alternative)

If file becomes too large (>10MB), use part files:

```python
# Write entities-part1.json, entities-part2.json, etc.
for batch_num in range(1, total_batches + 1):
    batch_file = f'entities-part{batch_num}.json'
    start = (batch_num - 1) * batch_size
    end = min(start + batch_size, len(entities))
    batch = entities[start:end]

    with open(batch_file, 'w') as f:
        json.dump({"entities": batch}, f, indent=2)

    print(f"<!-- BATCH {batch_num} of {total_batches} COMPLETE -->")

# Then merge all parts into final file
all_entities = []
for batch_num in range(1, total_batches + 1):
    with open(f'entities-part{batch_num}.json') as f:
        data = json.load(f)
        all_entities.extend(data['entities'])

# Write final merged file
with open('entities.pack.json', 'w') as f:
    json.dump({
        "schema": "https://legacylift.ai/schemas/entity.json",
        "packId": "pack:domain",
        "domain": "DomainName",
        "entities": all_entities
    }, f, indent=2)
```

### Critical Requirements:

1. **ALWAYS write in batches** for collections >100 items
2. **ALWAYS include batch markers** (`<!-- BATCH X of Y COMPLETE -->`)
3. **ALWAYS update TodoWrite** after each batch
4. **NEVER skip items** - write every single entity/relation/fact
5. **MAINTAIN deterministic order** - sort by ID before writing
6. **VALIDATE JSON** after each batch (well-formed)
7. **HANDLE context refresh** - resume from last batch marker

### Example Output with Markers:

```
<!-- Starting entity generation for LegalEntity domain -->
<!-- Processing 250 entities in 3 batches of 100 -->
<!-- BATCH 1 of 3 COMPLETE - entities 1-100 written -->
<!-- BATCH 2 of 3 COMPLETE - entities 101-200 written -->
<!-- BATCH 3 of 3 COMPLETE - entities 201-250 written -->
<!-- LegalEntity domain entities.pack.json complete: 250 entities -->
```

**This prevents memory issues, enables resumption after context refresh, and ensures ALL data is written.**

---

## ⚠️ MANDATORY OUTPUT REQUIREMENTS ⚠️

**THIS SKILL MUST GENERATE COMPLETE OUTPUT. NO EXCEPTIONS. NO SUMMARIES.**

### You MUST Generate ALL of the Following:

1. **ALL Entities** - Every single class, table, view, stored procedure, function found in the codebase
2. **ALL Relations** - Every inheritance, implementation, foreign key, dependency relationship
3. **ALL Facts** - Every property, validation, constraint, business rule with evidence
4. **Complete JSON Files** - All domain-scoped pack files + index.json

### Mandatory Batch Writing with Markers

**FOR LARGE ENTITY COLLECTIONS (>100 entities):**

Use incremental writing with `<!-- BATCH X of Y COMPLETE -->` markers:

```markdown
<!-- Starting entity generation -->
<!-- BATCH 1 of 10 COMPLETE -->
<!-- BATCH 2 of 10 COMPLETE -->
...
<!-- BATCH 10 of 10 COMPLETE -->
<!-- All entities written -->
```

**Pattern for Batch Writing:**

```python
# Example: Writing 500 entities in batches of 100
entities_total = 500
batch_size = 100
num_batches = (entities_total + batch_size - 1) // batch_size

for batch_num in range(1, num_batches + 1):
    start_idx = (batch_num - 1) * batch_size
    end_idx = min(start_idx + batch_size, entities_total)

    batch_entities = entities[start_idx:end_idx]

    # Write to file (append mode after first batch)
    mode = 'w' if batch_num == 1 else 'a'
    with open('entities.pack.json', mode) as f:
        if batch_num == 1:
            f.write('{\n  "entities": [\n')

        for i, entity in enumerate(batch_entities):
            f.write(json.dumps(entity, indent=4))
            if not (batch_num == num_batches and i == len(batch_entities) - 1):
                f.write(',\n')

        if batch_num == num_batches:
            f.write('\n  ]\n}\n')

    print(f"<!-- BATCH {batch_num} of {num_batches} COMPLETE -->")
```

**YOU MUST:**
- ✅ Write ALL entities (not samples, not examples, ALL)
- ✅ Write ALL relations (every single one)
- ✅ Write ALL facts with evidence
- ✅ Use batch writing for collections >100 items
- ✅ Include batch markers (`<!-- BATCH X of Y COMPLETE -->`)
- ✅ Generate complete, valid JSON files
- ✅ Create all 21 domain-scoped pack files (7 domains × 3 types)
- ✅ Generate index.json with complete statistics

**YOU MUST NOT:**
- ❌ Generate "sample" or "example" output
- ❌ Stop after extracting metadata
- ❌ Create summary documents instead of complete JSON
- ❌ Skip entities, relations, or facts
- ❌ Leave placeholders or TODOs

**Context Compaction Handling:**
- Save progress after each batch
- Use TodoWrite to track batch completion
- Resume from last completed batch after context refresh
- Maintain deterministic ordering (sort by ID)

---

## Extraction Process

The skill follows a systematic 6-phase approach to ensure deterministic, repeatable, and complete knowledge extraction.

**⚠️ CRITICAL: This skill uses DETERMINISTIC extraction only. No guessing, no inference, no LLM interpretation. Every fact must be grounded in verifiable code evidence.**

### Phase 1: Repository Discovery (Quick exploration)

**Objective**: Understand the codebase structure and identify what needs to be analyzed.

#### 1.1 Scan Repository Structure
- Use Glob to identify all source files
- Exclude build artifacts, node_modules, dist, bin, obj, target folders
- Exclude legacylift-docs folder (documentation output)
- Categorize files by extension

#### 1.2 Identify Programming Languages
```bash
# Count files by extension
*.cs     -> C# files
*.java   -> Java files
*.py     -> Python files
*.ts,*.tsx -> TypeScript files
*.js,*.jsx -> JavaScript files
*.sql,*.ddl -> SQL scripts
*.go     -> Go files
*.rs     -> Rust files
*.scala  -> Scala files
```

#### 1.3 Locate Key Files
- Configuration files (appsettings.json, package.json, pom.xml, build.gradle, etc.)
- Entry points (Program.cs, Main.java, app.py, index.ts, main.go)
- Database schemas (*.sql, *.ddl files)
- API definitions (controllers, routes, endpoints)

#### 1.4 Build File Inventory
Create a structured inventory by file type for Phase 2 processing:
```json
{
  "application_code": ["path/to/file1.cs", "path/to/file2.java"],
  "database_scripts": ["path/to/schema.sql", "path/to/procedures.sql"],
  "configuration": ["path/to/appsettings.json", "path/to/package.json"],
  "tests": ["path/to/test1.cs", "path/to/test2.py"]
}
```

#### 1.5 Count Lines of Code

Generate LOC metrics for the codebase to be included in the fact graph index. This step runs a single `cloc` command via `npx` and parses its JSON output.

**Objective:** Count lines of code by language, distinguishing blank lines, comment lines, and source code lines. Honor `.gitignore` rules so that git-ignored files are excluded automatically.

**Step 1: Check for a pre-existing cloc report.**

The `/legacylift-classic:cloc save=true` skill writes its output to `legacylift-docs/context/cloc-report.json` in the analyzed repository — the same directory where fact-graph stores `index.json` and pack files. If this file already exists from a prior run, use it directly and skip Steps 2 and 3:

```bash
test -f <path>/legacylift-docs/context/cloc-report.json && cat <path>/legacylift-docs/context/cloc-report.json
```

If the file exists and is valid JSON, read it as the `loc_metrics` input for Phase 6 (it already contains `total_loc`, `total_files`, and `by_language` in the format produced by Step 3 below). Skip to Phase 1.6.

If the file does not exist, continue with Step 2.

**Step 2: Determine whether the target path is a git repository.**

```bash
git -C <path> rev-parse --is-inside-work-tree 2>/dev/null
```

If the output is `true`, set `USE_GIT=true`. Otherwise set `USE_GIT=false`.

**Step 3: Run cloc with JSON output.**

When `USE_GIT=true`:

```bash
npx cloc --vcs=git --not-match-d=legacylift --json <path>
```

When `USE_GIT=false`:

```bash
npx cloc --not-match-d=legacylift --json <path>
```

If `npx` is not available (command not found or non-zero exit), fall back to storing an empty `loc_metrics` structure and proceed. Log a warning for the user.

Capture the JSON output.

**Step 4: Parse the cloc output into `loc_metrics`.**

Write the captured output to `/tmp/cloc_raw.json`, then run:

```bash
python3 -c "
import json, sys
data = json.load(open('/tmp/cloc_raw.json'))
total_sum = data.get('SUM', {})
total_loc = total_sum.get('blank', 0) + total_sum.get('comment', 0) + total_sum.get('code', 0)
total_files = total_sum.get('nFiles', 0)
by_language = {}
for lang, val in data.items():
    if lang in ('header', 'SUM'):
        continue
    if not isinstance(val, dict):
        continue
    blank   = val.get('blank', 0)
    comment = val.get('comment', 0)
    code    = val.get('code', 0)
    total   = blank + comment + code
    by_language[lang] = {
        'files':   val.get('nFiles', 0),
        'blank':   blank,
        'comment': comment,
        'code':    code,
        'total':   total
    }
result = {
    'total_loc':   total_loc,
    'total_files': total_files,
    'by_language': by_language
}
print(json.dumps(result))
"
```

Store the printed JSON as the `loc_metrics` value that is passed into Phase 6.

### Phase 1.6: Domain Classification

**Objective**: Identify **business domains** (not technical layers) to enable domain-scoped pack generation. Technical layers are captured as secondary attributes.

**⚠️ CRITICAL: Classify by BUSINESS DOMAIN first, then extract technical layer as metadata.**

- ✅ **Business Domain**: What business capability does this code support? (Orders, LegalEntity, Points, Billing)
- ✅ **Technical Layer** (secondary): How is it organized architecturally? (Model, Service, Persistence, Web)

**Example:**
- `com.nng.ple.service.point.PointService` → Domain: **Points**, Layer: **Service**
- `com.nng.ple.persistence.point.PointDao` → Domain: **Points**, Layer: **Persistence**
- `com.nng.ple.web.actions.point.PointAction` → Domain: **Points**, Layer: **Web**

All three entities belong to the **Points** business domain, with different technical layers.

#### 1.6.1 Analyze Namespace Patterns

Extract **business domain** from:
- **Database prefixes** (highest confidence): `LES*` → "LegalEntity", `POI*` → "Points", `ORD*` → "Orders"
- **Java packages** (domain segment): `com.nng.ple.{domain}.{layer}` or `com.nng.ple.{layer}.{domain}`
- **Folder structure**: Look for domain folder, not layer folder

Extract **technical layer** from:
- **Package segments**: `.model.`, `.service.`, `.persistence.`, `.web.`, `.util.`
- **Class suffixes**: `Dao`, `Service`, `Controller`, `Action`, `Validator`, `Util`
- **Folder names**: `/model/`, `/services/`, `/persistence/`, `/web/`

#### 1.6.2 Domain Classification Heuristics (Business-First)

**Priority 1: Database prefix-based (highest confidence)**
- `LES*` tables → "LegalEntity" domain
- `POI*` tables → "Points" domain
- `ORD*` tables → "Orders" domain
- `ETS*` tables → "EnergyTrading" domain
- Tables with `ple_` or generic prefixes → "Core" domain

**Priority 2: Business domain from namespace**
- Look for business domain keywords in package path
- Extract domain from: `com.{company}.{app}.{technical_layer}.{business_domain}`
  - `com.nng.ple.service.point` → Domain: **Points**
  - `com.nng.ple.persistence.legalentity` → Domain: **LegalEntity**
  - `com.nng.ple.model.order` → Domain: **Orders**

**Priority 3: Business domain from folder structure**
- Identify domain folder regardless of parent layer folder
- `/services/JavaSource/com/nng/ple/service/point/` → Domain: **Points**
- `/model/JavaSource/com/nng/ple/model/les/` → Domain: **LegalEntity**

**⚠️ AVOID: Don't classify by technical layer as domain**
- ❌ Don't create "Persistence" or "Web" or "Utilities" domains
- ❌ These are layers, not business domains
- ✅ Use technical_layer attribute instead

**Fallback for truly cross-cutting code:**
- Pure utilities (formatters, converters with no business logic) → "Core" domain
- Base classes, interfaces → "Core" domain
- Architecture/framework code → "Core" domain

**Test code classification:**
- Test files inherit domain from the code they test
- Pattern: `{Domain}Test.java` → same domain as `{Domain}.java`
- Location-based: `ple-services-test/.../point/` → "Points" domain

#### 1.6.3 Create Domain Mapping

Store domain classification in temporary file: `legacylift-docs/temp/domain-mapping.json`

```json
{
  "domains": {
    "Orders": {
      "namespaces": ["com.nng.ple.orders"],
      "folders": ["ple-services/JavaSource/com/nng/ple/orders"],
      "tables": ["POIOrder", "POIOrderItem"],
      "entity_count_estimate": 45
    },
    "LegalEntity": {
      "namespaces": ["com.nng.ple.legalentity", "com.nng.ple.model.les"],
      "folders": ["ple-model/JavaSource/com/nng/ple/model/les"],
      "tables": ["LESLegalEntity", "LESContact", "LESAddress"],
      "entity_count_estimate": 250
    },
    "Points": {
      "namespaces": ["com.nng.ple.point", "com.nng.ple.service.point"],
      "folders": ["ple-services/JavaSource/com/nng/ple/service/point"],
      "tables": ["POIPoint", "POIStation", "POIParty", "POIGroup"],
      "entity_count_estimate": 350
    }
  },
  "unclassified": {
    "reason": "No clear domain pattern",
    "entities": [],
    "fallback_domain": "Utilities"
  }
}
```

#### 1.6.4 Domain & Layer Classification Algorithm

```python
def classify_entity(entity_path: str, entity_qualified_name: str,
                   entity_type: str, entity_name: str) -> tuple[str, str]:
    """
    Classify an entity into business domain AND technical layer.
    Returns (domain_name, technical_layer)

    Domain: Business capability (e.g., "Orders", "LegalEntity", "Points")
    Layer: Technical layer (e.g., "Model", "Service", "Persistence", "Web", "Util")
    """

    domain = "Core"  # Default fallback
    layer = "Unknown"

    # Priority 1: Database entities - extract domain from prefix
    if entity_type in ["table", "view", "stored_proc"]:
        if entity_name.startswith("LES"):
            domain = "LegalEntity"
        elif entity_name.startswith("POI"):
            domain = "Points"
        elif entity_name.startswith("ORD"):
            domain = "Orders"
        elif entity_name.startswith("ETS"):
            domain = "EnergyTrading"
        elif entity_name.startswith("INV"):
            domain = "Inventory"
        elif entity_name.startswith("BILL") or entity_name.startswith("BIL"):
            domain = "Billing"
        elif entity_name.startswith("ple_") or entity_name.lower().startswith("dbo"):
            domain = "Core"

        # Database entities are always in "Persistence" layer
        layer = "Persistence"
        return domain, layer

    # Priority 2: Extract domain from namespace (business keywords)
    if entity_qualified_name:
        qn_lower = entity_qualified_name.lower()

        # Business domain keywords (NOT technical layer keywords)
        business_domains = {
            "legalentity": "LegalEntity",
            "les": "LegalEntity",
            "point": "Points",
            "poi": "Points",
            "order": "Orders",
            "edi": "EDI",
            "billing": "Billing",
            "inventory": "Inventory",
            "energytrading": "EnergyTrading",
            "ets": "EnergyTrading",
            "conflict": "Conflicts",
            "nomination": "Nominations",
            "schedule": "Scheduling",
            "contract": "Contracts"
        }

        # Check namespace parts for business domain
        parts = qn_lower.split(".")
        for part in parts:
            if part in business_domains:
                domain = business_domains[part]
                break

    # Priority 3: Extract domain from folder structure
    if domain == "Core" and entity_path:
        path_lower = entity_path.lower()

        if "legalentity" in path_lower or "/les/" in path_lower:
            domain = "LegalEntity"
        elif "point" in path_lower or "/poi/" in path_lower:
            domain = "Points"
        elif "order" in path_lower:
            domain = "Orders"
        elif "/edi/" in path_lower:
            domain = "EDI"
        elif "conflict" in path_lower:
            domain = "Conflicts"

    # Extract technical layer from namespace/path/class name
    if entity_qualified_name:
        qn_lower = entity_qualified_name.lower()

        # Technical layer keywords
        if ".model." in qn_lower or ".dto." in qn_lower or ".entity." in qn_lower:
            layer = "Model"
        elif ".service." in qn_lower:
            layer = "Service"
        elif ".persistence." in qn_lower or ".dao." in qn_lower or ".repository." in qn_lower:
            layer = "Persistence"
        elif ".web." in qn_lower or ".controller." in qn_lower or ".action." in qn_lower:
            layer = "Web"
        elif ".util." in qn_lower or ".helper." in qn_lower or ".converter." in qn_lower:
            layer = "Util"
        elif ".validator." in qn_lower:
            layer = "Validation"
        elif ".exception." in qn_lower or ".error." in qn_lower:
            layer = "Exception"
        elif ".config." in qn_lower or ".configuration." in qn_lower:
            layer = "Configuration"
        else:
            layer = "Other"

    # Classify truly cross-cutting utilities as Core domain
    if layer == "Util" and domain not in ["LegalEntity", "Points", "Orders", "EDI", "Billing", "Inventory", "EnergyTrading", "Conflicts", "Nominations", "Scheduling", "Contracts"]:
        domain = "Core"

    return domain, layer
```

#### 1.6.5 Validate Domain Classification

After classification, validate results:
- Each business domain should have at least 5 entities (warn if less)
- No single domain should contain more than 70% of entities (warn if so)
- "Core" domain should be < 15% of total entities (warn if higher - indicates too much cross-cutting code)
- Validate technical layer distribution: each domain should have entities in multiple layers (Model, Service, Persistence)

If validation fails, consider adjusting heuristics or using broader domain categories.

**CHECKPOINT: Mark "Phase 1.6: Domain Classification" as completed in TodoWrite**

---

### Phase 2: Entity Extraction (Systematic extraction)

**Objective**: Extract ALL entities from the codebase with precise location information.

#### 2.1 Entity Types to Extract

**Application Code Entities:**
- **Classes**: OOP class definitions
- **Interfaces**: Interface/trait/protocol definitions
- **Functions/Methods**: Callable units
- **Enums**: Enumeration types
- **DTOs**: Data Transfer Objects
- **Models**: Domain models
- **Services**: Service classes
- **Repositories**: Data access classes
- **Controllers**: API controllers
- **Endpoints**: API route handlers
- **Middleware**: Middleware/interceptors
- **Components**: UI components

**Database Entities:**
- **Tables**: CREATE TABLE definitions
- **Views**: CREATE VIEW definitions
- **Stored Procedures**: CREATE PROCEDURE definitions
- **SQL Functions**: CREATE FUNCTION definitions
- **Triggers**: CREATE TRIGGER definitions
- **Indexes**: CREATE INDEX definitions
- **Constraints**: PRIMARY KEY, FOREIGN KEY, UNIQUE, CHECK constraints

**Configuration Entities:**
- **Config Sections**: Configuration sections from JSON/XML/YAML
- **Environment Variables**: ENV var usage
- **Feature Flags**: Feature toggle definitions

**⚠️ CRITICAL: Execute entity extraction in batches by language/technology with TodoWrite checkpoints between each batch to survive context refresh.**

**Workflow Pattern:**
1. Execute Batch 1 (Java entities) - extract and save to temp JSON
2. Mark Batch 1 todo as completed
3. Execute Batch 2 (C# entities) - extract and save to temp JSON
4. Mark Batch 2 todo as completed
5. Continue for all batches
6. Merge all temp JSON files into final entities.pack.json

**Entity Extraction Batching:**
- **Batch 1**: Java entities (classes, interfaces, enums, methods)
- **Batch 2**: C# entities (classes, interfaces, methods, controllers)
- **Batch 3**: Python entities (classes, functions, decorators)
- **Batch 4**: JavaScript/TypeScript entities (classes, functions, components)
- **Batch 5**: SQL/Database entities (tables, views, procedures, functions)
- **Batch 6**: Other languages (Go, Rust, Ruby, PHP, etc.)

#### 2.2 Extraction Techniques by Language (Execute in Batches)

##### C# Extraction
```bash
# Classes
grep -n "^\s*public\s+class\s+\w+" *.cs --include="*.cs" -r

# Interfaces
grep -n "^\s*public\s+interface\s+\w+" *.cs --include="*.cs" -r

# Methods
grep -n "^\s*public.*\s+\w+\s*\(" *.cs --include="*.cs" -r

# Controllers (ASP.NET)
grep -n ":\s*ControllerBase\|:\s*Controller" *.cs --include="*.cs" -r

# Endpoints (Minimal API)
grep -n "app\.Map(Get|Post|Put|Delete|Patch)" *.cs --include="*.cs" -r
```

**After extracting C# entities, save to temp JSON file (entities-csharp.json) and mark todo as completed.**

**CHECKPOINT: Update TodoWrite - Mark "Extract Entities Batch 2 (C#)" as completed**

---

##### Java Extraction
```bash
# Classes
grep -n "^\s*public\s+class\s+\w+" *.java --include="*.java" -r

# Interfaces
grep -n "^\s*public\s+interface\s+\w+" *.java --include="*.java" -r

# Spring Controllers
grep -n "@RestController\|@Controller" *.java --include="*.java" -r

# Spring Endpoints
grep -n "@GetMapping\|@PostMapping\|@PutMapping\|@DeleteMapping" *.java --include="*.java" -r
```

**After extracting Java entities, save to temp JSON file (entities-java.json) and mark todo as completed.**

**CHECKPOINT: Update TodoWrite - Mark "Extract Entities Batch 1 (Java)" as completed**

---

##### Python Extraction
```bash
# Classes
grep -n "^class\s+\w+" *.py --include="*.py" -r

# Functions
grep -n "^def\s+\w+" *.py --include="*.py" -r

# FastAPI endpoints
grep -n "@app\.(get|post|put|delete|patch)" *.py --include="*.py" -r

# Flask routes
grep -n "@app\.route\|@blueprint\.route" *.py --include="*.py" -r
```

**After extracting Python entities, save to temp JSON file (entities-python.json) and mark todo as completed.**

**CHECKPOINT: Update TodoWrite - Mark "Extract Entities Batch 3 (Python)" as completed**

---

##### TypeScript/JavaScript Extraction
```bash
# Classes
grep -n "^export\s+class\s+\w+\|^class\s+\w+" *.ts *.tsx *.js *.jsx --include="*.ts" --include="*.tsx" -r

# Functions
grep -n "^export\s+function\s+\w+\|^function\s+\w+\|^const\s+\w+\s*=\s*\(" *.ts *.tsx *.js *.jsx -r

# Interfaces
grep -n "^export\s+interface\s+\w+\|^interface\s+\w+" *.ts *.tsx -r

# Express routes
grep -n "router\.(get|post|put|delete|patch)\|app\.(get|post|put|delete|patch)" *.ts *.js -r

# React components
grep -n "^export\s+(default\s+)?function\s+\w+\|^const\s+\w+:\s*React\.FC" *.tsx *.jsx -r
```

**After extracting JavaScript/TypeScript entities, save to temp JSON file (entities-js-ts.json) and mark todo as completed.**

**CHECKPOINT: Update TodoWrite - Mark "Extract Entities Batch 4 (JS/TS)" as completed**

---

##### SQL Extraction
```bash
# Tables
grep -n "CREATE\s+TABLE" *.sql *.ddl --include="*.sql" --include="*.ddl" -r -i

# Views
grep -n "CREATE\s+VIEW" *.sql *.ddl -r -i

# Stored Procedures
grep -n "CREATE\s+(OR\s+REPLACE\s+)?PROCEDURE" *.sql *.ddl -r -i

# Functions
grep -n "CREATE\s+(OR\s+REPLACE\s+)?FUNCTION" *.sql *.ddl -r -i

# Triggers
grep -n "CREATE\s+TRIGGER" *.sql *.ddl -r -i
```

**After extracting SQL/Database entities, save to temp JSON file (entities-sql.json) and mark todo as completed.**

**CHECKPOINT: Update TodoWrite - Mark "Extract Entities Batch 5 (SQL/Database)" as completed**

---

##### Other Languages (Go, Rust, Ruby, PHP, etc.)
For other languages, extract entities and save to entities-other.json.

**After extracting other language entities, save to temp JSON file (entities-other.json) and mark todo as completed.**

**CHECKPOINT: Update TodoWrite - Mark "Extract Entities Batch 6 (Other Languages)" as completed**

---

##### Phase 2c: Generate Complete Entity JSON with Proper IDs and Domain Classification

**⚠️ CRITICAL: This is NOT just merging temp files. You MUST generate ALL entity JSON with complete metadata.**

**YOU MUST:**

1. **Load ALL extracted entity metadata** from Task agents or temp files
   - Java entities (ALL 224+ entities, not samples)
   - SQL entities (ALL 531+ entities - tables, views, stored procs)
   - Other language entities (if any)

2. **For EACH entity, generate proper JSON structure:**
   ```python
   for each_entity in all_extracted_entities:
       # Classify into business domain AND technical layer
       domain, technical_layer = classify_entity(
           entity_path=entity.file,
           entity_qualified_name=entity.qualified_name,
           entity_type=entity.type,
           entity_name=entity.name
       )

       # Generate deterministic ID
       entity_id = generate_entity_id(
           entity_type=entity.type,
           qualified_name=entity.qualified_name,
           file_path=entity.file,
           domain=domain
       )

       # Calculate content hash for drift detection
       content_hash = calculate_content_hash(entity.file, entity.line_range)

       # Create complete entity object
       entity_json = {
           "id": entity_id,
           "type": entity.type,
           "name": entity.name,
           "qualified_name": entity.qualified_name,
           "file": entity.file,
           "line_range": entity.line_range,
           "attributes": {
               "language": entity.language,
               "domain": domain,                    # Business domain
               "technical_layer": technical_layer,  # Technical layer (NEW)
               "content_hash": content_hash,
               # ... all other attributes
           }
       }
   ```

3. **Classify each entity into business domain AND technical layer:**
   - **Domain** (business capability): Use table prefixes (LES*, POI*), namespace patterns, folder structure
   - **Technical Layer** (architecture): Extract from package segments (.model., .service., .persistence., .web.)
   - Example: `com.nng.ple.service.point.PointService` → Domain: **Points**, Layer: **Service**
   - Fallback domain: "Core" (for truly cross-cutting utilities)

4. **Group entities by domain:**
   ```python
   domains = {
       "LegalEntity": [],
       "Points": [],
       "EDI": [],
       "EnergyTrading": [],
       "Web": [],
       "Conflicts": [],
       "Utilities": []
   }

   for entity in all_entities:
       domain = entity["attributes"]["domain"]
       domains[domain].append(entity)
   ```

5. **Write domain-scoped entity pack files:**
   - For EACH domain, write `{domain}.entities.pack.json`
   - Use batch writing with markers for large collections
   - Sort entities by ID for determinism

   ```python
   for domain_name, domain_entities in domains.items():
       # Sort by ID
       domain_entities.sort(key=lambda e: e["id"])

       # Write with batch markers
       write_entities_batch(
           filename=f"{domain_name.lower()}.entities.pack.json",
           entities=domain_entities,
           batch_size=100
       )

       print(f"<!-- {domain_name} domain: {len(domain_entities)} entities written -->")
   ```

6. **Validate completeness:**
   - Count entities written vs. entities extracted
   - Verify no duplicates
   - Verify all IDs are properly formatted
   - Verify all files are valid JSON

**Expected Output from Phase 2c:**
```
legacylift-docs/context/packs/
├── legalentity.entities.pack.json    # ~250 entities
├── points.entities.pack.json         # ~350 entities
├── edi.entities.pack.json            # ~50 entities
├── energytrading.entities.pack.json  # ~30 entities
├── web.entities.pack.json            # ~180 entities
├── conflicts.entities.pack.json      # ~40 entities
└── utilities.entities.pack.json      # ~100 entities
```

**Total entities across all packs MUST equal total entities extracted (755+).**

**CHECKPOINT: Update TodoWrite - Mark "Phase 2c: Generate Complete Entity JSON" as completed**

---

#### 2.3 Entity ID Generation

**Critical**: Entity IDs must use domain-prefixed format for semantic clarity and determinism.

**ID Prefix Strategy:**
- `cs:` - Classes, services, components (C#, Java, TypeScript)
- `db:` - Database tables
- `ep:` - API endpoints
- `auth:` - Authentication/authorization entities
- `svc:` - Service classes
- `dto:` - Data transfer objects
- `proc:` - Stored procedures
- `view:` - Database views
- `trig:` - Database triggers
- `ent:` - Generic entities (fallback)

**ID Format:** `{prefix}:{domain}-{normalized_name}-{hash}`

**Example:** `cs:orders-orderservice-abc123`

```python
import hashlib

def generate_entity_id(entity_type: str, qualified_name: str, file_path: str, domain: str) -> str:
    """Generate deterministic entity ID with domain prefix"""

    # Determine prefix based on entity type
    prefix_map = {
        "class": "cs",
        "interface": "cs",
        "service": "svc",
        "table": "db",
        "view": "view",
        "stored_proc": "proc",
        "endpoint": "ep",
        "dto": "dto",
        "enum": "cs",
        "controller": "cs",
        "repository": "cs"
    }
    prefix = prefix_map.get(entity_type.lower(), "ent")

    # Normalize domain and name
    domain_lower = domain.lower().replace(" ", "").replace("_", "")
    name_normalized = qualified_name.split(".")[-1].lower().replace("_", "")

    # Generate hash for uniqueness
    content = f"{entity_type}:{qualified_name}:{file_path}"
    hash_digest = hashlib.sha256(content.encode()).hexdigest()[:12]

    # Format: prefix:domain-name-hash
    return f"{prefix}:{domain_lower}-{name_normalized}-{hash_digest}"
```

**Usage:**
```python
# Java class in Orders domain
entity_id = generate_entity_id("class", "com.nng.ple.orders.OrderService",
                               "ple-services/JavaSource/com/nng/ple/orders/OrderService.java",
                               "Orders")
# Result: "cs:orders-orderservice-a3b5c7d9e1f2"

# SQL table in LegalEntity domain
entity_id = generate_entity_id("table", "dbo.LESLegalEntity",
                               "customer.ple.nng.db.ETSPii/ScriptsFolder/Tables/dbo.LESLegalEntity.Table.sql",
                               "LegalEntity")
# Result: "db:legalentity-leslegalentity-f9a8b7c6d5e4"
```

#### 2.4 Entity Extraction Output

For each discovered entity, create an entry with prefixed ID and content hash:

```json
{
  "id": "cs:usermanagement-userservice-abc123",
  "type": "class",
  "name": "UserService",
  "qualified_name": "MyApp.Services.UserService",
  "file": "src/Services/UserService.cs",
  "line_range": [10, 150],
  "attributes": {
    "language": "csharp",
    "visibility": "public",
    "namespace": "MyApp.Services",
    "is_abstract": false,
    "is_static": false,
    "implements": ["IUserService"],
    "domain": "UserManagement",
    "capability": "UserAuthentication",
    "content_hash": "a3b5c7d9e1f2"
  }
}
```

**Content Hash Calculation:**

The `content_hash` enables drift detection by citation-validator skill.

```python
def calculate_content_hash(file_path: str, line_range: List[int]) -> str:
    """Calculate SHA-256 hash of entity code block for drift detection"""
    with open(file_path, 'r') as f:
        lines = f.readlines()

    start, end = line_range
    code_block = ''.join(lines[start-1:end])

    # Hash the code block
    return hashlib.sha256(code_block.encode()).hexdigest()[:12]
```

**Domain/Capability Classification:**
- **Domain**: Business domain the entity belongs to (e.g., "OrderManagement", "UserManagement", "Payment")
- **Capability**: Specific capability within the domain (e.g., "OrderProcessing", "UserAuthentication", "PaymentValidation")

**Classification Heuristics:**
1. **Namespace-based**: Extract from namespace structure (e.g., `MyApp.Orders.Processing` → domain: "Orders", capability: "Processing")
2. **Folder-based**: Extract from file path (e.g., `src/Orders/Processing/` → domain: "Orders", capability: "Processing")
3. **Naming convention**: Entity name patterns (e.g., `OrderProcessingService` → domain: "Orders", capability: "OrderProcessing")
4. **Manual configuration**: Allow optional domain mapping config file

**Content Hash:**
- **Purpose**: Enable drift detection for citation-validator
- **Calculation**: SHA-256 hash of entity code block (from line_range)
- **Format**: First 12 characters of hex digest
- **Usage**: Compare hash to detect when code has changed near citations

### Phase 3: Relation Extraction (Relationship mapping)

**Objective**: Identify and extract relationships between entities.

**⚠️ CRITICAL: Execute relation extraction in batches by relation type with TodoWrite checkpoints between each batch to survive context refresh.**

**Workflow Pattern:**
1. Execute Batch 1 (Inheritance & Implementation) - extract and save to temp JSON
2. Mark Batch 1 todo as completed
3. Execute Batch 2 (Containment) - extract and save to temp JSON
4. Mark Batch 2 todo as completed
5. Continue for all batches
6. Merge all temp JSON files into final relations.pack.json

**Relation Extraction Batching:**
- **Batch 1**: Inheritance & Implementation relations (inherits, implements, extends)
- **Batch 2**: Containment relations (contains, has_member, owns)
- **Batch 3**: Dependency relations (uses, calls, invokes, references, imports)
- **Batch 4**: Database relations (foreign_key, join)
- **Batch 5**: Metadata relations (decorates, annotates, routes_to, triggers)

---

#### 3.1 Relation Types to Extract

**Inheritance & Implementation:**
- `inherits`: Class extends another class
- `implements`: Class implements an interface
- `extends`: General extension relationship

**Dependencies:**
- `uses`: General usage/dependency
- `calls`: Method/function invocation
- `invokes`: Explicit method call
- `references`: Property/field reference
- `imports`: Module/namespace import
- `depends_on`: Build/package dependency

**Structure:**
- `contains`: Containment (class contains method, service contains endpoint)
- `owns`: Ownership relationship
- `has_member`: Class has member

**Data Access:**
- `reads_from`: Reading data (code → database)
- `writes_to`: Writing data (code → database)
- `queries`: SQL query execution

**Database:**
- `foreign_key`: Foreign key constraint
- `join`: Table join relationship

**Metadata:**
- `triggers`: Trigger relationship
- `decorates`: Decorator/attribute application
- `annotates`: Annotation application
- `routes_to`: Routing relationship

#### 3.2 Extraction Techniques

##### Batch 1: Inheritance & Implementation
Extract inheritance and implementation relations (inherits, implements, extends).

```bash
# C# - Class inheritance
grep -n ":\s*\w+\s*\(,\|$\)" *.cs --include="*.cs" -r

# Java - implements/extends
grep -n "implements\s+\w+\|extends\s+\w+" *.java --include="*.java" -r

# Python - class inheritance
grep -n "class\s+\w+\s*\(" *.py --include="*.py" -r

# TypeScript - implements/extends
grep -n "implements\s+\w+\|extends\s+\w+" *.ts *.tsx --include="*.ts" -r
```

**After extracting inheritance & implementation relations, save to temp JSON file (relations-inheritance.json) and mark todo as completed.**

**CHECKPOINT: Update TodoWrite - Mark "Extract Relations Batch 1 (Inheritance & Implementation)" as completed**

---

##### Batch 2: Containment Relations
Extract containment relations (contains, has_member, owns).

```bash
# Classes contain methods - match entities extracted in Phase 2
# For each class entity, find all method entities in the same file
# Create "contains" relations between class and its methods

# Services contain endpoints - match controller methods
# For each service/controller entity, find endpoint methods
```

**After extracting containment relations, save to temp JSON file (relations-containment.json) and mark todo as completed.**

**CHECKPOINT: Update TodoWrite - Mark "Extract Relations Batch 2 (Containment)" as completed**

---

##### Batch 3: Dependency Relations
Extract dependency relations (uses, calls, invokes, references, imports).

```bash
# Method Calls - Identify method invocations
# For each method entity, search for its usage in other files
# Example: For method "GetUserById", search for "GetUserById("

# Import statements
grep -n "^import\s+\|^from\s+.*\s+import" *.py --include="*.py" -r
grep -n "^import\s+" *.ts *.tsx *.js *.jsx --include="*.ts" --include="*.tsx" --include="*.js" -r
grep -n "^using\s+" *.cs --include="*.cs" -r
```

**After extracting dependency relations, save to temp JSON file (relations-dependencies.json) and mark todo as completed.**

**CHECKPOINT: Update TodoWrite - Mark "Extract Relations Batch 3 (Dependencies)" as completed**

---

##### Batch 4: Database Relations
Extract database relations (foreign_key, join).

```bash
# SQL foreign keys
grep -n "FOREIGN\s+KEY.*REFERENCES" *.sql *.ddl -r -i

# ORM foreign keys (Hibernate, Entity Framework)
grep -n "@ManyToOne\|@OneToMany\|@OneToOne\|@ManyToMany" *.java --include="*.java" -r
grep -n "ForeignKey\|HasOne\|HasMany\|WithMany" *.cs --include="*.cs" -r
```

**After extracting database relations, save to temp JSON file (relations-database.json) and mark todo as completed.**

**CHECKPOINT: Update TodoWrite - Mark "Extract Relations Batch 4 (Database)" as completed**

---

##### Batch 5: Metadata Relations
Extract metadata relations (decorates, annotates, routes_to, triggers).

```bash
# Decorators/Attributes
grep -n "@\w+\|^\s*\[\w+\]" *.java *.cs *.py *.ts --include="*.java" --include="*.cs" --include="*.py" --include="*.ts" -r

# Route annotations
grep -n "@RequestMapping\|@GetMapping\|@PostMapping\|@Route\|@HttpGet\|@HttpPost" *.java *.cs --include="*.java" --include="*.cs" -r
```

**After extracting metadata relations, save to temp JSON file (relations-metadata.json) and mark todo as completed.**

**CHECKPOINT: Update TodoWrite - Mark "Extract Relations Batch 5 (Metadata)" as completed**

---

##### Merge All Relation Batches
**Final step**: Merge all temp JSON files into final relations.pack.json:
- Load relations-inheritance.json
- Load relations-containment.json
- Load relations-dependencies.json
- Load relations-database.json
- Load relations-metadata.json
- Combine all relations into single array
- Sort by relation ID for deterministic output
- Save to legacylift-docs/context/packs/relations.pack.json

**CHECKPOINT: Update TodoWrite - Mark "Merge Relation Batches" as completed**

---

#### 3.3 Relation ID Generation

```python
def generate_relation_id(relation_type: str, source_id: str, target_id: str) -> str:
    """Generate deterministic relation ID"""
    content = f"{relation_type}:{source_id}:{target_id}"
    hash_digest = hashlib.sha256(content.encode()).hexdigest()[:12]
    return f"rel-{relation_type}-{hash_digest}"
```

#### 3.4 Relation Extraction Output

```json
{
  "id": "rel-implements-abc123",
  "type": "implements",
  "source_id": "class-userservice-xyz789",
  "target_id": "interface-iuserservice-def456",
  "file": "src/Services/UserService.cs",
  "line": 10,
  "attributes": {
    "via": "interface implementation"
  }
}
```

### Phase 4: Fact Extraction (Verifiable claims)

**Objective**: Extract verifiable facts about entities with evidence.

**⚠️ CRITICAL: Execute fact extraction in batches by fact type with TodoWrite checkpoints between each batch to survive context refresh.**

**Workflow Pattern:**
1. Execute Batch 1 (Properties & Attributes) - extract and save to temp JSON
2. Mark Batch 1 todo as completed
3. Execute Batch 2 (Validation & Constraints) - extract and save to temp JSON
4. Mark Batch 2 todo as completed
5. Continue for all batches
6. Merge all temp JSON files into final facts.pack.json

**Fact Extraction Batching:**
- **Batch 1**: Properties & Attributes (has_property, has_attribute, has_method, has_field, has_column)
- **Batch 2**: Validation & Constraints (validates, requires, max_length, is_required, is_nullable, is_unique, is_indexed)
- **Batch 3**: Integration & Configuration (integrates_with, authenticates_via, default_value, timeout_after)
- **Batch 4**: Data Operations & Workflow (stores_in, reads_from, writes_to, caches_in, state_transition, process_step)
- **Batch 5**: HTTP Metadata & Business Rules (http_method, accepts_param, returns_response, requires_auth, business_rule)

---

#### 4.0 Confidence Scoring Guidelines

**⚠️ CRITICAL**: All facts MUST include a confidence object with score and reasoning. This enables consumers to assess fact reliability.

**Confidence Score Ranges:**

- **1.0**: Extracted from explicit keyword/annotation
  - Examples: `public` modifier, `@Authorize` attribute, `PRIMARY KEY` constraint
  - Reasoning: "Extracted directly from 'public' modifier in class declaration"

- **0.9-0.95**: Extracted from clear, unambiguous pattern
  - Examples: Naming conventions (DAO suffix), folder structure, method signatures
  - Reasoning: "Inferred from DAO suffix in class name and location in persistence package"

- **0.7-0.85**: Inferred from context or related entities
  - Examples: Related entities, common patterns, architectural conventions
  - Reasoning: "Inferred from relationship to UserService and standard repository pattern"

- **0.5-0.65**: Heuristic guess based on weak signals
  - Examples: Fuzzy name matching, indirect evidence
  - Reasoning: "Heuristic guess based on similar naming pattern in related classes"

- **< 0.5**: Hypothesis only (should be flagged or excluded)
  - Low confidence facts should not be included unless explicitly marked as hypothetical

**Snippet Hash for Drift Detection:**

Every evidence entry MUST include a `snippet_hash` calculated from the code snippet:

```python
def calculate_snippet_hash(snippet: str) -> str:
    """Calculate SHA-256 hash of evidence snippet for drift detection"""
    # Normalize whitespace
    normalized = ' '.join(snippet.strip().split())
    return hashlib.sha256(normalized.encode()).hexdigest()[:12]
```

This enables the citation-validator skill to detect when code has changed and facts may be outdated.

---

#### 4.1 Fact Types to Extract

**Properties & Attributes:**
- `has_property`: Entity has a property/field
- `has_attribute`: Entity has an attribute/annotation
- `has_method`: Entity has a method
- `has_field`: Entity has a field
- `has_column`: Table has a column

**Validation & Constraints:**
- `validates`: Validation rule
- `requires`: Required constraint
- `max_length`: Maximum length constraint
- `min_value`: Minimum value constraint
- `max_value`: Maximum value constraint
- `pattern_matches`: Regex pattern constraint
- `is_required`: Field is required
- `is_nullable`: Field is nullable
- `is_unique`: Field must be unique
- `is_indexed`: Field is indexed

**Behavior:**
- `throws`: Exception throwing
- `returns`: Return type
- `accepts`: Parameter type
- `ensures`: Postcondition

**Integration:**
- `integrates_with`: External system integration
- `authenticates_via`: Authentication mechanism
- `authorizes_via`: Authorization mechanism

**Data Operations:**
- `stores_in`: Storage location
- `reads_from`: Data source
- `writes_to`: Data destination
- `caches_in`: Cache location
- `logs_to`: Logging destination
- `publishes_to`: Event/message publishing
- `subscribes_to`: Event/message subscription

**Configuration:**
- `default_value`: Default value
- `triggers_on`: Trigger condition
- `timeout_after`: Timeout configuration

**Workflow & State Machines:**
- `state_transition`: State transition (from state A to state B)
- `process_step`: Workflow process step

**HTTP Endpoint Metadata:**
- `http_method`: HTTP method (GET, POST, PUT, DELETE, etc.)
- `accepts_param`: Request parameter definition
- `returns_response`: Response format/DTO
- `requires_auth`: Authentication requirement

**Relationship Metadata:**
- `has_cardinality`: Relationship cardinality (one-to-many, many-to-many, one-to-one)

**Business Rules:**
- `business_rule`: Complex business rule (beyond simple constraints)

#### 4.2 Extraction Examples

##### Batch 1: Properties & Attributes

###### Property Extraction (C#)
```bash
# Public properties
grep -n "public\s+\w+\s+\w+\s*{\s*get" *.cs --include="*.cs" -r
```

For each property found, create a fact:
```json
{
  "id": "fact-userservice-has-property-connectionstring",
  "subject_id": "cs:userservice-userservice-abc123",
  "predicate": "has_property",
  "object": "ConnectionString",
  "evidence": [
    {
      "file": "src/Services/UserService.cs",
      "line_range": [15, 15],
      "snippet": "public string ConnectionString { get; set; }",
      "snippet_hash": "a1b2c3d4e5f6"
    }
  ],
  "confidence": {
    "score": 1.0,
    "reasoning": "Extracted directly from property declaration with explicit 'public' modifier and data type"
  },
  "attributes": {
    "data_type": "string",
    "visibility": "public"
  }
}
```

###### Database Column Facts (SQL)
```bash
# Table columns with constraints
grep -n "^\s*\w+\s+\w+.*NOT NULL\|^\s*\w+\s+\w+.*PRIMARY KEY" *.sql -r -i
```

For each column:
```json
{
  "id": "fact-users-has-column-userid",
  "subject_id": "db:users-users-abc",
  "predicate": "has_column",
  "object": "UserId",
  "evidence": [
    {
      "file": "database/schema/users.sql",
      "line_range": [3, 3],
      "snippet": "UserId INT PRIMARY KEY NOT NULL",
      "snippet_hash": "b2c3d4e5f6a1"
    }
  ],
  "confidence": {
    "score": 1.0,
    "reasoning": "Extracted directly from CREATE TABLE DDL statement with explicit column definition, data type, and constraints"
  },
  "attributes": {
    "data_type": "INT",
    "is_nullable": false,
    "is_unique": true
  }
}
```

**After extracting properties & attributes facts, save to temp JSON file (facts-properties.json) and mark todo as completed.**

**CHECKPOINT: Update TodoWrite - Mark "Extract Facts Batch 1 (Properties & Attributes)" as completed**

---

##### Batch 2: Validation & Constraints

###### Validation Rule Extraction
```bash
# FluentValidation (C#)
grep -n "RuleFor.*\.NotEmpty()\|RuleFor.*\.MaximumLength(" *.cs -r

# Data annotations (C#)
grep -n "\[Required\]\|\[MaxLength(" *.cs -r

# Python validators
grep -n "@validator\|@validates" *.py -r
```

For each validation found, create a fact:
```json
{
  "id": "fact-user-validates-email-required",
  "subject_id": "cs:user-usermodel-xyz",
  "predicate": "is_required",
  "object": "Email",
  "evidence": [
    {
      "file": "src/Models/User.cs",
      "line_range": [12, 13],
      "snippet": "[Required]\npublic string Email { get; set; }",
      "snippet_hash": "c3d4e5f6a1b2"
    }
  ],
  "confidence": {
    "score": 1.0,
    "reasoning": "Extracted directly from [Required] data annotation attribute on Email property"
  },
  "attributes": {
    "constraint_type": "Required"
  }
}
```

**After extracting validation & constraints facts, save to temp JSON file (facts-validations.json) and mark todo as completed.**

**CHECKPOINT: Update TodoWrite - Mark "Extract Facts Batch 2 (Validation & Constraints)" as completed**

---

##### Batch 3: Integration & Configuration

###### Integration Facts
```bash
# External service clients
grep -n "HttpClient\|RestClient\|WebClient" *.cs *.java *.py -r
grep -n "AWS\|Azure\|Google Cloud" *.cs *.java *.py -r
```

For each integration:
```json
{
  "id": "fact-authservice-integrates-azuread",
  "subject_id": "svc:identity-authservice-xyz",
  "predicate": "integrates_with",
  "object": "AzureAD",
  "evidence": [
    {
      "file": "src/Services/AuthService.cs",
      "line_range": [45, 52],
      "snippet": "private readonly IAzureAdClient _azureAdClient;\npublic AuthService(IAzureAdClient azureAdClient)",
      "snippet_hash": "d4e5f6a1b2c3"
    }
  ],
  "confidence": {
    "score": 0.95,
    "reasoning": "Inferred from dependency injection of IAzureAdClient interface in constructor, strongly indicating Azure AD integration"
  },
  "attributes": {
    "provider": "Microsoft.Identity"
  }
}
```

**After extracting integration & configuration facts, save to temp JSON file (facts-integrations.json) and mark todo as completed.**

**CHECKPOINT: Update TodoWrite - Mark "Extract Facts Batch 3 (Integration & Configuration)" as completed**

---

##### Batch 4: Data Operations & Workflow

###### State Transition Facts (Workflows)
```bash
# Search for state transitions in code (status updates, state changes)
grep -n "Status\s*=\|State\s*=\|\.Status\s*=\|\.State\s*=" *.cs *.java *.py -r
grep -n "OrderStatus\|UserStatus\|PaymentStatus" *.cs *.java -r
grep -n "switch.*Status\|switch.*State" *.cs *.java -r
```

For each state transition:
```json
{
  "id": "fact-order-state-transition-abc123",
  "subject_id": "svc:orders-orderservice-xyz789",
  "predicate": "state_transition",
  "object": "Pending→Approved",
  "evidence": [
    {
      "file": "src/Services/OrderService.cs",
      "line_range": [45, 52],
      "snippet": "if (paymentVerified) {\n  order.Status = OrderStatus.Approved;\n}",
      "snippet_hash": "e5f6a1b2c3d4"
    }
  ],
  "confidence": {
    "score": 0.9,
    "reasoning": "Extracted from explicit Status property assignment within conditional logic, clear state transition pattern"
  },
  "attributes": {
    "from_state": "Pending",
    "to_state": "Approved",
    "condition": "payment verified",
    "trigger": "payment verification"
  }
}
```

**After extracting data operations & workflow facts, save to temp JSON file (facts-operations.json) and mark todo as completed.**

**CHECKPOINT: Update TodoWrite - Mark "Extract Facts Batch 4 (Data Operations & Workflow)" as completed**

---

##### Batch 5: HTTP Metadata & Business Rules

###### HTTP Endpoint Metadata Facts
```bash
# FastEndpoints (C#)
grep -n "Post\(\".*\"\)\|Get\(\".*\"\)\|Put\(\".*\"\)\|Delete\(\".*\"\)" *.cs -r

# ASP.NET attributes
grep -n "\[HttpPost\]\|\[HttpGet\]\|\[HttpPut\]\|\[HttpDelete\]" *.cs -r
grep -n "\[Route\(" *.cs -r

# Spring (Java)
grep -n "@PostMapping\|@GetMapping\|@PutMapping\|@DeleteMapping" *.java -r

# FastAPI/Flask (Python)
grep -n "@app\.post\|@app\.get\|@app\.put\|@app\.delete" *.py -r
```

For each endpoint:
```json
{
  "id": "fact-createorder-http-method-xyz456",
  "subject_id": "ep:orders-createorderendpoint-abc789",
  "predicate": "http_method",
  "object": "POST",
  "evidence": [
    {
      "file": "src/Api/Endpoints/CreateOrderEndpoint.cs",
      "line_range": [26, 26],
      "snippet": "Post(\"/api/orders\");",
      "snippet_hash": "f6a1b2c3d4e5"
    }
  ],
  "confidence": {
    "score": 1.0,
    "reasoning": "Extracted directly from Post() method call with explicit route definition"
  },
  "attributes": {
    "route": "/api/orders",
    "auth_required": true,
    "request_dto": "CreateOrderRequest",
    "response_dto": "OrderDto",
    "http_status_success": 200
  }
}
```

For request parameters:
```json
{
  "id": "fact-createorder-accepts-param-def123",
  "subject_id": "ep:orders-createorderendpoint-abc789",
  "predicate": "accepts_param",
  "object": "CreateOrderRequest",
  "evidence": [
    {
      "file": "src/Api/Endpoints/CreateOrderEndpoint.cs",
      "line_range": [30, 30],
      "snippet": "public override async Task HandleAsync(CreateOrderRequest req, CancellationToken ct)",
      "snippet_hash": "a1b2c3d4e5f6"
    }
  ],
  "confidence": {
    "score": 1.0,
    "reasoning": "Extracted directly from HandleAsync method signature with explicit parameter type CreateOrderRequest"
  },
  "attributes": {
    "param_type": "body",
    "data_type": "CreateOrderRequest",
    "required": true
  }
}
```

##### Relationship Cardinality Facts
```bash
# ORM annotations (C#)
grep -n "\[ForeignKey\]\|\[InverseProperty\]" *.cs -r

# Java Hibernate/JPA
grep -n "@OneToMany\|@ManyToOne\|@ManyToMany\|@OneToOne" *.java -r

# Entity Framework Core navigation properties
grep -n "ICollection<\|List<\|virtual.*ICollection\|virtual.*List" *.cs -r
```

For each relationship:
```json
{
  "id": "fact-order-has-cardinality-ghi789",
  "subject_id": "relation-order-orderitems-jkl012",
  "predicate": "has_cardinality",
  "object": "one-to-many",
  "evidence": [
    {
      "file": "src/Models/Order.cs",
      "line_range": [25, 25],
      "snippet": "public virtual ICollection<OrderItem> OrderItems { get; set; }",
      "snippet_hash": "b2c3d4e5f6a1"
    }
  ],
  "confidence": {
    "score": 0.95,
    "reasoning": "Inferred from ICollection<OrderItem> navigation property, standard Entity Framework pattern for one-to-many relationships"
  },
  "attributes": {
    "cardinality": "one-to-many",
    "parent_entity": "Order",
    "child_entity": "OrderItem",
    "cascade_delete": true
  }
}
```

##### Business Rule Facts (Complex Rules)
```bash
# Conditional business logic
grep -n "if.*amount.*>\|if.*price.*>\|if.*threshold" *.cs *.java *.py -r
grep -n "requires.*approval\|needs.*approval\|must.*approve" *.cs *.java *.py -r

# Business calculations
grep -n "Calculate.*Total\|Calculate.*Tax\|Calculate.*Discount" *.cs *.java *.py -r

# Business validations
grep -n "BusinessException\|BusinessValidation\|BusinessRule" *.cs *.java -r
```

For each complex business rule:
```json
{
  "id": "fact-order-business-rule-mno345",
  "subject_id": "svc:orders-orderservice-pqr678",
  "predicate": "business_rule",
  "object": "Orders over $1000 require manager approval",
  "evidence": [
    {
      "file": "src/Services/OrderService.cs",
      "line_range": [78, 85],
      "snippet": "if (order.TotalAmount > 1000) {\n  order.RequiresApproval = true;\n  await _notificationService.NotifyManager(order);\n}",
      "snippet_hash": "c3d4e5f6a1b2"
    }
  ],
  "confidence": {
    "score": 0.85,
    "reasoning": "Inferred from conditional logic checking TotalAmount > 1000 with approval flag and manager notification, clear business rule pattern"
  },
  "attributes": {
    "rule_type": "approval",
    "threshold": 1000,
    "threshold_type": "amount",
    "action": "require_manager_approval",
    "description": "High-value orders require manager approval"
  }
}
```

**After extracting HTTP metadata & business rules facts, save to temp JSON file (facts-http-rules.json) and mark todo as completed.**

**CHECKPOINT: Update TodoWrite - Mark "Extract Facts Batch 5 (HTTP Metadata & Business Rules)" as completed**

---

##### Merge All Fact Batches
**Final step**: Merge all temp JSON files into final facts.pack.json:
- Load facts-properties.json
- Load facts-validations.json
- Load facts-integrations.json
- Load facts-operations.json
- Load facts-http-rules.json
- Combine all facts into single array
- Sort by fact ID for deterministic output
- Save to legacylift-docs/context/packs/facts.pack.json

**CHECKPOINT: Update TodoWrite - Mark "Merge Fact Batches" as completed**

---

#### 4.3 Fact ID Generation

```python
def generate_fact_id(subject_id: str, predicate: str, object_value: str) -> str:
    """Generate deterministic fact ID"""
    content = f"{subject_id}:{predicate}:{object_value}"
    hash_digest = hashlib.sha256(content.encode()).hexdigest()[:12]
    return f"fact-{hash_digest}"
```

#### 4.4 Evidence Requirements

**Every fact MUST have evidence:**
1. File path (relative to repo root)
2. Line range [start, end] (1-indexed, inclusive)
3. Optional: Code snippet for human readability

**Evidence Quality:**
- Line ranges should be tight (typically 1-10 lines)
- Must point to the exact location where the fact is grounded
- File path must be correct and verifiable
- Multiple evidence entries allowed for facts supported by multiple locations

### Phase 5: Evidence Collection & Validation (Quality assurance)

**Objective**: Ensure all extracted data has verifiable evidence.

**⚠️ CRITICAL: Execute validation in batches by data type with TodoWrite checkpoints between each batch to survive context refresh.**

**Workflow Pattern:**
1. Execute Batch 1 (Validate Entities) - verify file existence, line validity, content
2. Mark Batch 1 todo as completed
3. Execute Batch 2 (Validate Relations) - verify reference integrity, file existence
4. Mark Batch 2 todo as completed
5. Execute Batch 3 (Validate Facts) - verify evidence, file existence
6. Mark Batch 3 todo as completed
7. Execute Batch 4 (Check Duplicate IDs) - ensure uniqueness across all collections
8. Mark Batch 4 todo as completed

**Validation Batching:**
- **Batch 1**: Validate Entities (file existence, line validity, content verification)
- **Batch 2**: Validate Relations (reference integrity - check source_id and target_id exist in entities, file existence)
- **Batch 3**: Validate Facts (evidence verification - check subject_id exists, file existence, line validity)
- **Batch 4**: Check Duplicate IDs (ensure no duplicate IDs across entities, relations, facts)

---

#### 5.1 Validation Checks

##### Batch 1: Validate Entities
For each entity:
1. **File Existence**: Verify file path exists
2. **Line Validity**: Verify line numbers are within file bounds
3. **Content Verification**: Read file and verify line range contains relevant code

**After validating all entities, mark todo as completed.**

**CHECKPOINT: Update TodoWrite - Mark "Validate Entities" as completed**

---

##### Batch 2: Validate Relations
For each relation:
1. **Reference Integrity**: Verify source_id and target_id reference existing entities
2. **File Existence**: Verify file path exists
3. **Line Validity**: Verify line number is within file bounds

**After validating all relations, mark todo as completed.**

**CHECKPOINT: Update TodoWrite - Mark "Validate Relations" as completed**

---

##### Batch 3: Validate Facts
For each fact:
1. **Subject Reference**: Verify subject_id references existing entity or relation
2. **Evidence Verification**: For each evidence entry, verify file exists and line range is valid
3. **Content Verification**: Read file and verify evidence snippet exists at specified lines

**After validating all facts, mark todo as completed.**

**CHECKPOINT: Update TodoWrite - Mark "Validate Facts" as completed**

---

##### Batch 4: Check Duplicate IDs
Check for duplicate IDs across all collections:
1. **Entity ID Uniqueness**: Ensure all entity IDs are unique
2. **Relation ID Uniqueness**: Ensure all relation IDs are unique
3. **Fact ID Uniqueness**: Ensure all fact IDs are unique
4. **Cross-Collection Uniqueness**: Ensure no ID appears in multiple collections

**After checking duplicate IDs, mark todo as completed.**

**CHECKPOINT: Update TodoWrite - Mark "Check Duplicate IDs" as completed**

#### 5.2 Evidence Collection

```python
def collect_evidence(file: str, start_line: int, end_line: int) -> dict:
    """Collect evidence from file"""
    with open(file, 'r') as f:
        lines = f.readlines()

    # Validate line range
    if start_line < 1 or end_line > len(lines):
        raise ValueError(f"Invalid line range {start_line}-{end_line} for file {file}")

    # Extract snippet
    snippet_lines = lines[start_line-1:end_line]
    snippet = ''.join(snippet_lines).strip()

    return {
        "file": file,
        "line_range": [start_line, end_line],
        "snippet": snippet
    }
```

#### 5.3 Duplicate Detection

Check for duplicate IDs:
```python
def validate_uniqueness(entities, relations, facts):
    """Ensure all IDs are unique"""
    all_ids = []
    all_ids.extend([e["id"] for e in entities])
    all_ids.extend([r["id"] for r in relations])
    all_ids.extend([f["id"] for f in facts])

    duplicates = [id for id in all_ids if all_ids.count(id) > 1]
    if duplicates:
        raise ValueError(f"Duplicate IDs found: {set(duplicates)}")
```

### Phase 6: JSON Generation & Serialization (Domain-Scoped Packs)

**Objective**: Serialize extracted knowledge to domain-scoped JSON packs for selective loading and scalability.

**⚠️ CRITICAL CHANGE: This phase generates DOMAIN-SCOPED packs, not single monolithic packs.**

#### 6.1 Group Entities by Domain

**Objective**: Group all entities by their domain classification to enable domain-scoped pack generation.

```python
def group_entities_by_domain(entities: List[Dict]) -> Dict[str, List[Dict]]:
    """Group entities by their domain attribute"""
    domains = {}
    for entity in entities:
        domain = entity.get("attributes", {}).get("domain", "Utilities")
        if domain not in domains:
            domains[domain] = []
        domains[domain].append(entity)
    return domains
```

**Example Output:**
```python
{
  "LegalEntity": [entity1, entity2, ...],  # 250 entities
  "Points": [entity3, entity4, ...],        # 350 entities
  "GasOperations": [entity5, entity6, ...], # 80 entities
  "Persistence": [entity7, entity8, ...],   # 200 entities
  "Web": [entity9, entity10, ...],          # 180 entities
  "Utilities": [entity11, entity12, ...]    # 106 entities
}
```

#### 6.2 Sort All Collections

**Critical for Determinism**: All arrays must be sorted consistently.

```python
# Sort entities by ID (within each domain)
for domain_name, domain_entities in domains.items():
    domain_entities.sort(key=lambda e: e["id"])

# Sort relations by ID
relations.sort(key=lambda r: r["id"])

# Sort facts by ID
facts.sort(key=lambda f: f["id"])
```

#### 6.3 Project Classification

**Objective**: Classify the project type and architecture pattern using heuristics.

**Classification Categories:**

**Project Types:**
- `monolith`: Single application codebase
- `microservices`: Multiple independent services
- `monorepo`: Multiple related projects in one repository
- `library`: Reusable library/package
- `cli_tool`: Command-line application
- `web_app`: Web application (frontend or full-stack)
- `mobile_app`: Mobile application
- `unknown`: Unable to determine

**Architecture Patterns:**
- `layered`: Traditional layered architecture (presentation, business, data)
- `mvc`: Model-View-Controller pattern
- `mvvm`: Model-View-ViewModel pattern
- `clean`: Clean architecture (hexagonal, onion)
- `microservices`: Distributed microservices architecture
- `serverless`: Serverless functions
- `event_driven`: Event-driven architecture
- `cqrs`: Command Query Responsibility Segregation
- `unknown`: Unable to determine

**Classification Heuristics:**

```python
def classify_project(entities, files_analyzed, repo_root):
    """Classify project type and architecture pattern"""
    import os

    project_type = "unknown"
    architecture_pattern = "unknown"

    # Detect project type
    # Check for Docker/K8s (microservices indicators)
    has_docker = os.path.exists(f"{repo_root}/Dockerfile") or \
                 os.path.exists(f"{repo_root}/docker-compose.yml")
    has_k8s = os.path.exists(f"{repo_root}/k8s") or \
              os.path.exists(f"{repo_root}/kubernetes")

    # Check for multiple service directories
    service_dirs = [d for d in os.listdir(repo_root)
                    if os.path.isdir(f"{repo_root}/{d}") and
                    ('service' in d.lower() or 'api' in d.lower())]
    has_multiple_services = len(service_dirs) > 1

    # Check for package definition (library)
    is_library = os.path.exists(f"{repo_root}/setup.py") or \
                 os.path.exists(f"{repo_root}/package.json") and \
                 not os.path.exists(f"{repo_root}/src/index.html")

    # Check for CLI indicators
    is_cli = any(e.get("name", "").lower() in ["cli", "main", "program"]
                 for e in entities if e.get("type") == "class")

    # Determine project type
    if has_multiple_services or (has_docker and has_k8s):
        project_type = "microservices"
    elif has_multiple_services and not has_k8s:
        project_type = "monorepo"
    elif is_library:
        project_type = "library"
    elif is_cli:
        project_type = "cli_tool"
    elif any(e.get("type") == "controller" for e in entities):
        project_type = "web_app"
    else:
        project_type = "monolith"

    # Detect architecture pattern
    # Check for MVC (controllers, models, views)
    has_controllers = any(e.get("type") == "controller" for e in entities)
    has_models = any("model" in e.get("name", "").lower() for e in entities)
    has_views = any("view" in e.get("name", "").lower() for e in entities)

    if has_controllers and has_models and has_views:
        architecture_pattern = "mvc"
    elif has_controllers and has_models:
        architecture_pattern = "mvc"

    # Check for layered architecture (namespace/folder patterns)
    namespaces = [e.get("attributes", {}).get("namespace", "") for e in entities]
    has_layers = any("presentation" in ns.lower() or "business" in ns.lower() or
                     "data" in ns.lower() or "infrastructure" in ns.lower()
                     for ns in namespaces)

    if has_layers:
        architecture_pattern = "layered"

    # Check for Clean Architecture indicators
    has_core = any("core" in ns.lower() or "domain" in ns.lower() for ns in namespaces)
    has_infrastructure = any("infrastructure" in ns.lower() for ns in namespaces)
    has_application = any("application" in ns.lower() for ns in namespaces)

    if has_core and has_infrastructure and has_application:
        architecture_pattern = "clean"

    # Check for CQRS (commands, queries, handlers)
    has_commands = any("command" in e.get("name", "").lower() for e in entities)
    has_queries = any("query" in e.get("name", "").lower() for e in entities)
    has_handlers = any("handler" in e.get("name", "").lower() for e in entities)

    if has_commands and has_queries and has_handlers:
        architecture_pattern = "cqrs"

    # Microservices architecture
    if project_type == "microservices":
        architecture_pattern = "microservices"

    return project_type, architecture_pattern
```

**Usage in Index Generation:**
```python
# During Phase 6, before generating index
project_type, architecture_pattern = classify_project(entities, files_analyzed, repo_root)

# Group entities by domain
domains = group_entities_by_domain(entities)

# Pass to generate_index function with domain info
index = generate_index(entities, relations, facts, domains, repo_name, files_analyzed,
                       loc_metrics, project_type, architecture_pattern)
```

#### 6.4 Generate Index File with Pack Metadata

```python
import json
from datetime import datetime

def generate_index(entities, relations, facts, domains, repo_name, files_analyzed, loc_metrics,
                   project_type="unknown", architecture_pattern="unknown"):
    """Generate index.json with LOC metrics, project classification, and domain pack metadata"""
    # Calculate statistics
    entity_types = {}
    for entity in entities:
        entity_type = entity["type"]
        entity_types[entity_type] = entity_types.get(entity_type, 0) + 1

    relation_types = {}
    for relation in relations:
        relation_type = relation["type"]
        relation_types[relation_type] = relation_types.get(relation_type, 0) + 1

    languages = {}
    for entity in entities:
        if "language" in entity.get("attributes", {}):
            lang = entity["attributes"]["language"]
            languages[lang] = languages.get(lang, 0) + 1

    # Calculate percentages for LOC by language (cloc output)
    total_loc = loc_metrics.get("total_loc", 0)
    by_language = {}
    for lang, metrics in loc_metrics.get("by_language", {}).items():
        total_lines = metrics.get("total", 0)
        percentage = round((total_lines / total_loc * 100), 1) if total_loc > 0 else 0
        by_language[lang] = {
            "files":      metrics.get("files", 0),
            "blank":      metrics.get("blank", 0),
            "comment":    metrics.get("comment", 0),
            "code":       metrics.get("code", 0),
            "total":      total_lines,
            "percentage": percentage
        }

    # Generate pack metadata for each domain
    packs_metadata = []
    for domain_name, domain_entities in domains.items():
        domain_lower = domain_name.lower().replace(" ", "").replace("_", "")

        # Extract keywords from entity names
        keywords = set()
        for entity in domain_entities:
            # Add entity name tokens
            name_parts = entity["name"].lower().split("_")
            keywords.update(name_parts)

            # Add qualified name tokens
            if "qualified_name" in entity:
                qn_parts = entity["qualified_name"].lower().split(".")
                keywords.update(qn_parts[-2:])  # Last 2 segments

        # Remove common/generic words
        stop_words = {"class", "interface", "service", "model", "dto", "entity", "table", "view"}
        keywords = [kw for kw in keywords if kw not in stop_words and len(kw) > 2]

        pack_meta = {
            "packId": f"pack:{domain_lower}",
            "domain": domain_name,
            "files": {
                "entities": f"packs/{domain_lower}.entities.pack.json",
                "relations": f"packs/{domain_lower}.relations.pack.json",
                "facts": f"packs/{domain_lower}.facts.pack.json"
            },
            "entity_count": len(domain_entities),
            "keywords": sorted(list(set(keywords)))[:20]  # Top 20 unique keywords
        }
        packs_metadata.append(pack_meta)

    # Sort packs by entity count descending (largest domains first)
    packs_metadata.sort(key=lambda p: p["entity_count"], reverse=True)

    return {
        "metadata": {
            "repository": repo_name,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "tool_version": "1.0.0",
            "analysis_scope": "full",
            "project_type": project_type,
            "architecture_pattern": architecture_pattern
        },
        "statistics": {
            "entity_count": len(entities),
            "relation_count": len(relations),
            "fact_count": len(facts),
            "files_analyzed": files_analyzed,
            "entity_types": entity_types,
            "relation_types": relation_types,
            "languages": languages,
            "lines_of_code": {
                "total_loc":   loc_metrics.get("total_loc", 0),
                "total_files": loc_metrics.get("total_files", 0),
                "by_language": by_language,
                "methodology": "cloc --vcs=git (total = blank + comment + code; git-tracked files only; legacylift* directories excluded)"
            },
            "packs_metadata": packs_metadata
        },
        "packs": {
            "note": "This repository uses domain-scoped packs. See packs_metadata for details."
        },
        "schema_version": "1.0"
    }
```

#### 6.5 Generate Domain-Scoped Pack Files

```python
def generate_domain_packs(domains: Dict[str, List[Dict]], relations: List[Dict], facts: List[Dict], output_dir: str):
    """Generate domain-scoped pack files for entities, relations, and facts"""
    import json
    import os

    # Create packs directory
    os.makedirs(f"{output_dir}/context/packs", exist_ok=True)

    # For each domain, generate three pack files
    for domain_name, domain_entities in domains.items():
        domain_lower = domain_name.lower().replace(" ", "").replace("_", "")

        # Extract entity IDs for this domain
        entity_ids = set(e["id"] for e in domain_entities)

        # Filter relations for this domain (source_id or target_id in entity_ids)
        domain_relations = [
            r for r in relations
            if r["source_id"] in entity_ids or r["target_id"] in entity_ids
        ]

        # Filter facts for this domain (subject_id in entity_ids)
        domain_facts = [
            f for f in facts
            if f["subject_id"] in entity_ids
        ]

        # Generate entities pack
        entities_pack = {
            "schema": "https://legacylift.ai/schemas/entity.json",
            "packId": f"pack:{domain_lower}",
            "domain": domain_name,
            "entities": sorted(domain_entities, key=lambda e: e["id"])
        }

        # Generate relations pack
        relations_pack = {
            "schema": "https://legacylift.ai/schemas/relation.json",
            "packId": f"pack:{domain_lower}",
            "domain": domain_name,
            "relations": sorted(domain_relations, key=lambda r: r["id"])
        }

        # Generate facts pack
        facts_pack = {
            "schema": "https://legacylift.ai/schemas/fact.json",
            "packId": f"pack:{domain_lower}",
            "domain": domain_name,
            "facts": sorted(domain_facts, key=lambda f: f["id"])
        }

        # Write domain-scoped pack files
        with open(f"{output_dir}/context/packs/{domain_lower}.entities.pack.json", 'w') as f:
            json.dump(entities_pack, f, indent=2, ensure_ascii=False)

        with open(f"{output_dir}/context/packs/{domain_lower}.relations.pack.json", 'w') as f:
            json.dump(relations_pack, f, indent=2, ensure_ascii=False)

        with open(f"{output_dir}/context/packs/{domain_lower}.facts.pack.json", 'w') as f:
            json.dump(facts_pack, f, indent=2, ensure_ascii=False)

        print(f"✓ Generated packs for domain '{domain_name}': {len(domain_entities)} entities, {len(domain_relations)} relations, {len(domain_facts)} facts")
```

#### 6.6 Write JSON Files

```python
def write_json_files(output_dir, index, domains, relations, facts):
    """Write index and all domain-scoped pack files"""
    import os
    import json

    # Create directory structure
    os.makedirs(f"{output_dir}/context/packs", exist_ok=True)

    # Write index
    with open(f"{output_dir}/context/index.json", 'w') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    # Generate domain-scoped packs
    generate_domain_packs(domains, relations, facts, output_dir)

    print(f"\n✓ Generated index.json with {len(domains)} domain packs")
```

### Phase 7: Cleanup Temporary Files

**Objective**: Remove intermediate processing files to keep the output directory clean and professional.

**⚠️ CRITICAL: Only run cleanup AFTER all pack files and index.json have been successfully generated and validated.**

#### 7.1 Preserve Critical Files

**Keep these files (do NOT delete):**
- `index.json` - Master index
- `packs/*.pack.json` - All domain-scoped pack files (entities, relations, facts)
- `README.md` - Documentation (if generated)

**Optional: Keep extraction summary**
- Consider keeping a lightweight extraction summary/log for debugging

#### 7.2 Remove Temporary Files

**Delete these temporary files:**
- `temp/entities-java.json` - Intermediate Java entities
- `temp/entities-sql.json` - Intermediate SQL entities
- `temp/entities-*.json` - Other language entity files
- `temp/relations-*.json` - Intermediate relation files
- `temp/facts-*.json` - Intermediate fact files
- `temp/domain-mapping.json` - Domain classification metadata
- `temp/file-inventory.json` - File inventory
- `temp/*.py` - Processing scripts
- `temp/*.sh` - Shell scripts
- `temp/*.txt` - Temporary text files
- `temp/entity-stats.json` - Temporary statistics (included in index.json)

**Remove temp directory entirely:**
```bash
rm -rf legacylift-docs/context/temp/
```

Or use Python:
```python
import shutil
import os

temp_dir = 'legacylift-docs/context/temp'
if os.path.exists(temp_dir):
    shutil.rmtree(temp_dir)
    print(f"✓ Cleaned up temporary files in {temp_dir}")
```

#### 7.3 Final Output Structure

After cleanup, the output directory should contain:

```
legacylift-docs/context/
├── index.json                        # Master index (10-20 KB)
├── README.md                         # Documentation (optional)
└── packs/                           # Domain-scoped packs
    ├── {domain1}.entities.pack.json
    ├── {domain1}.relations.pack.json
    ├── {domain1}.facts.pack.json
    ├── {domain2}.entities.pack.json
    ├── {domain2}.relations.pack.json
    ├── {domain2}.facts.pack.json
    └── ...
```

**Total files:** 1 + (N domains × 3) + 1 (optional README)

**Example:** 8 domains = 1 + (8 × 3) + 1 = 26 files total

#### 7.4 Verification

Before completing, verify:
- ✅ index.json exists and is valid JSON
- ✅ All expected pack files exist (N domains × 3 types)
- ✅ Pack files are valid JSON
- ✅ temp/ directory has been removed
- ✅ No intermediate processing files remain

**CHECKPOINT: Update TodoWrite - Mark "Phase 7: Cleanup Temporary Files" as completed**

---

### Extraction Strategy

**Phase 1-2: Discovery & Entities** (Parallel Execution)
- Launch Task/Explore agents for each language
- Agent 1: Extract C# entities
- Agent 2: Extract SQL entities
- Agent 3: Extract TypeScript entities
- Merge results into unified entity collection

**Phase 3-4: Relations & Facts** (Sequential with Entities)
- Use entity results from Phase 2
- Extract relations between known entities
- Extract facts about known entities
- Validate references

**Phase 5-6: Validation & Serialization** (Sequential)
- Validate all data
- Sort collections
- Generate JSON files
- Write to output directory

**Phase 7: Cleanup** (Final)
- Remove temporary processing files
- Keep only final output (index.json, packs/, README.md)
- Verify output structure is clean and professional

## Success Criteria

Fact graph generation is considered complete when:

✅ All source files have been scanned
✅ Entities extracted for all supported languages and classified by business domain
✅ Relations extracted for all entity pairs
✅ Facts extracted with evidence for all entities
✅ All IDs are unique (no duplicates)
✅ All relation references are valid (source/target IDs exist)
✅ All evidence file paths and line ranges are valid
✅ JSON output is well-formed and schema-compliant
✅ Statistics are accurate (counts match collections)
✅ Output is deterministic (repeatable)
✅ Index file generated with metadata and domain statistics
✅ All pack files generated (entities, relations, facts) grouped by business domain
✅ Each entity has both domain and technical_layer attributes
✅ Temporary files cleaned up (temp/ directory removed)
✅ Output directory contains only production files

## Expected Output: What You MUST Generate

### Mandatory Files (NO EXCEPTIONS)

**File Count Formula:**
```
Total Files = 1 + (N × 3)
```
Where:
- **1** = index.json (always required)
- **N** = Number of domains identified in Phase 1.6
- **3** = Files per domain (entities.pack.json, relations.pack.json, facts.pack.json)

**Example: Repository with 7 domains → 22 files total**
- 1 index.json
- 7 × 3 = 21 domain pack files
- **Total: 1 + 21 = 22 files**

**Example: Repository with 5 domains → 16 files total**
- 1 index.json
- 5 × 3 = 15 domain pack files
- **Total: 1 + 15 = 16 files**

---

**You MUST generate:**

1. **index.json** (1 file) - Master index with complete statistics

2. **Domain-scoped entity packs** (N files, where N = number of domains) - One per domain
   - Example for 7 domains:
     - `legalentity.entities.pack.json`
     - `points.entities.pack.json`
     - `edi.entities.pack.json`
     - `energytrading.entities.pack.json`
     - `web.entities.pack.json`
     - `conflicts.entities.pack.json`
     - `utilities.entities.pack.json`

3. **Domain-scoped relation packs** (N files) - One per domain
   - Example for 7 domains:
     - `legalentity.relations.pack.json`
     - `points.relations.pack.json`
     - `edi.relations.pack.json`
     - `energytrading.relations.pack.json`
     - `web.relations.pack.json`
     - `conflicts.relations.pack.json`
     - `utilities.relations.pack.json`

4. **Domain-scoped fact packs** (N files) - One per domain
   - Example for 7 domains:
     - `legalentity.facts.pack.json`
     - `points.facts.pack.json`
     - `edi.facts.pack.json`
     - `energytrading.facts.pack.json`
     - `web.facts.pack.json`
     - `conflicts.facts.pack.json`
     - `utilities.facts.pack.json`

### File Structure Example

```
legacylift-docs/context/
├── index.json                                  # 10-20 KB
└── packs/
    ├── legalentity.entities.pack.json         # 100-200 KB
    ├── legalentity.relations.pack.json        # 50-150 KB
    ├── legalentity.facts.pack.json            # 150-300 KB
    ├── points.entities.pack.json              # 150-250 KB
    ├── points.relations.pack.json             # 80-180 KB
    ├── points.facts.pack.json                 # 200-400 KB
    ├── edi.entities.pack.json                 # 20-50 KB
    ├── edi.relations.pack.json                # 10-30 KB
    ├── edi.facts.pack.json                    # 30-80 KB
    ├── energytrading.entities.pack.json       # 15-40 KB
    ├── energytrading.relations.pack.json      # 8-25 KB
    ├── energytrading.facts.pack.json          # 20-60 KB
    ├── web.entities.pack.json                 # 80-150 KB
    ├── web.relations.pack.json                # 40-100 KB
    ├── web.facts.pack.json                    # 100-200 KB
    ├── conflicts.entities.pack.json           # 20-50 KB
    ├── conflicts.relations.pack.json          # 10-30 KB
    ├── conflicts.facts.pack.json              # 30-80 KB
    ├── utilities.entities.pack.json           # 50-100 KB
    ├── utilities.relations.pack.json          # 20-60 KB
    └── utilities.facts.pack.json              # 50-120 KB
```

### Content Requirements per Pack File

**entities.pack.json** - MUST contain:
```json
{
  "schema": "https://legacylift.ai/schemas/entity.json",
  "packId": "pack:legalentity",
  "domain": "LegalEntity",
  "entities": [
    {
      "id": "cs:legalentity-leslegalentity-abc123",
      "type": "class",
      "name": "LeslegalEntity",
      "qualified_name": "com.nng.ple.model.LeslegalEntity",
      "file": "ple-model/JavaSource/com/nng/ple/model/LeslegalEntity.java",
      "line_range": [34, 200],
      "attributes": {
        "language": "java",
        "package": "com.nng.ple.model",
        "is_abstract": false,
        "superclass": "AbstractPleModel",
        "interfaces": ["Serializable"],
        "domain": "LegalEntity",
        "content_hash": "a3b5c7d9e1f2"
      }
    }
    // ... ALL other entities for this domain (NO SAMPLES, ALL ENTITIES)
  ]
}
```

**relations.pack.json** - MUST contain:
```json
{
  "schema": "https://legacylift.ai/schemas/relation.json",
  "packId": "pack:legalentity",
  "domain": "LegalEntity",
  "relations": [
    {
      "id": "rel-inherits-xyz789",
      "type": "inherits",
      "source_id": "cs:legalentity-leslegalentity-abc123",
      "target_id": "cs:utilities-abstractplemodel-def456",
      "file": "ple-model/JavaSource/com/nng/ple/model/LeslegalEntity.java",
      "line": 34,
      "attributes": {
        "via": "class extension"
      }
    }
    // ... ALL relations for this domain
  ]
}
```

**facts.pack.json** - MUST contain:
```json
{
  "schema": "https://legacylift.ai/schemas/fact.json",
  "packId": "pack:legalentity",
  "domain": "LegalEntity",
  "facts": [
    {
      "id": "fact-leslegalentity-has-property-abc",
      "subject_id": "cs:legalentity-leslegalentity-abc123",
      "predicate": "has_property",
      "object": "legalEntityNumber",
      "evidence": [
        {
          "file": "ple-model/JavaSource/com/nng/ple/model/LeslegalEntity.java",
          "line_range": [48, 48],
          "snippet": "private Integer legalEntityNumber;",
          "snippet_hash": "c1d2e3f4a5b6"
        }
      ],
      "confidence": {
        "score": 1.0,
        "reasoning": "Extracted directly from field declaration"
      },
      "attributes": {
        "data_type": "Integer",
        "visibility": "private"
      }
    }
    // ... ALL facts for this domain
  ]
}
```

### Validation Checklist Before Completion

Before marking the skill as complete, verify:

- [ ] Generated correct number of files using formula: 1 + (N domains × 3)
  - Example: 7 domains = 22 files (1 index + 21 packs)
  - Example: 5 domains = 16 files (1 index + 15 packs)
- [ ] Each domain has exactly 3 pack files (entities, relations, facts)
- [ ] ALL entities from extraction are in pack files (not samples)
- [ ] ALL relations are documented
- [ ] ALL facts have evidence with file paths and line numbers
- [ ] Index.json has accurate counts matching pack file contents
- [ ] All JSON files are valid and well-formed
- [ ] All IDs are unique across entire graph
- [ ] All relation references point to existing entity IDs
- [ ] All fact subject IDs point to existing entities
- [ ] All file paths in evidence are valid and exist
- [ ] Files are sorted deterministically (by ID)
- [ ] Batch markers are present for large collections

**IF ANY OF THE ABOVE ARE MISSING, THE SKILL EXECUTION IS INCOMPLETE.**

## Skill Execution

When this skill is invoked, I will:

1. **Parse Parameters**
   - Repository path (default: current directory)
   - Output directory (default: `{repo}/legacylift-docs/context/`)
   - Analysis scope (full or domain-specific)

2. **Create Todo List**
   - Phase 1.1: Repository Discovery - Scan structure
   - Phase 1.2: Repository Discovery - Identify languages
   - Phase 1.3: Repository Discovery - Locate key files
   - Phase 1.4: Repository Discovery - Build file inventory
   - Phase 1.5a: Count LOC Batch 1 (JVM Languages)
   - Phase 1.5b: Count LOC Batch 2 (.NET Languages)
   - Phase 1.5c: Count LOC Batch 3 (JavaScript/TypeScript)
   - Phase 1.5d: Count LOC Batch 4 (Database/SQL)
   - Phase 1.5e: Count LOC Batch 5 (Python)
   - Phase 1.5f: Count LOC Batch 6 (Web Frontend)
   - Phase 1.5g: Count LOC Batch 7 (Configuration Files)
   - Phase 1.5h: Count LOC Batch 8 (Build/Scripts)
   - Phase 1.5i: Count LOC Batch 9 (Other Languages)
   - Phase 2a: Extract Entities Batch 1 (Java)
   - Phase 2b: Extract Entities Batch 2 (C#)
   - Phase 2c: Extract Entities Batch 3 (Python)
   - Phase 2d: Extract Entities Batch 4 (JS/TS)
   - Phase 2e: Extract Entities Batch 5 (SQL/Database)
   - Phase 2f: Extract Entities Batch 6 (Other Languages)
   - Phase 2g: Merge Entity Batches
   - Phase 3a: Extract Relations Batch 1 (Inheritance & Implementation)
   - Phase 3b: Extract Relations Batch 2 (Containment)
   - Phase 3c: Extract Relations Batch 3 (Dependencies)
   - Phase 3d: Extract Relations Batch 4 (Database)
   - Phase 3e: Extract Relations Batch 5 (Metadata)
   - Phase 3f: Merge Relation Batches
   - Phase 4a: Extract Facts Batch 1 (Properties & Attributes)
   - Phase 4b: Extract Facts Batch 2 (Validation & Constraints)
   - Phase 4c: Extract Facts Batch 3 (Integration & Configuration)
   - Phase 4d: Extract Facts Batch 4 (Data Operations & Workflow)
   - Phase 4e: Extract Facts Batch 5 (HTTP Metadata & Business Rules)
   - Phase 4f: Merge Fact Batches
   - Phase 5a: Validate Entities
   - Phase 5b: Validate Relations
   - Phase 5c: Validate Facts
   - Phase 5d: Check Duplicate IDs
   - Phase 6: JSON Generation & Serialization
   - Phase 7: Cleanup Temporary Files

3. **Execute Extraction**
   - Use Glob to find all source files
   - Use Grep to search for entity patterns
   - Use Read to parse detailed information
   - Use Task to launch parallel extraction agents
   - Validate all extracted data

4. **Generate Output**
   - Create deterministic IDs for all items
   - Sort all collections
   - Generate index.json with metadata
   - Generate pack files (entities, relations, facts)
   - Write files to output directory

5. **Cleanup and Finalize**
   - Remove temporary processing files (temp/ directory)
   - Verify final output structure is clean
   - Ensure only production files remain

6. **Provide Summary**
   - Total entities extracted (breakdown by type and domain)
   - Total relations extracted (breakdown by type)
   - Total facts extracted
   - Files analyzed count
   - Domains identified
   - Output location and file count
   - Technical layer distribution per domain

## Supporting Files & Templates

This skill uses supporting files in the `templates/` directory to define the JSON schema and data model.

### Template Structure

| Template File | Purpose | Usage |
|---------------|---------|-------|
| **[entity.schema.json](./templates/entity.schema.json)** | JSON Schema for entity validation | Defines structure, required fields, and validation rules for entities |
| **[relation.schema.json](./templates/relation.schema.json)** | JSON Schema for relation validation | Defines structure, required fields, and validation rules for relations |
| **[fact.schema.json](./templates/fact.schema.json)** | JSON Schema for fact validation | Defines structure, required fields, and validation rules for facts |
| **[index.schema.json](./templates/index.schema.json)** | JSON Schema for index validation | Defines structure for master index file with metadata and pack references |
| **[README.md](./templates/README.md)** | Schema documentation | Comprehensive documentation on data model, schema usage, examples, and best practices |

### How Templates Are Used

During skill execution:

1. **Reference Schemas**: Load JSON schemas to understand data structure
2. **Validate Output**: Validate generated JSON against schemas (optional but recommended)
3. **Follow Patterns**: Use examples from README as templates for extraction
4. **Maintain Consistency**: Ensure all output follows schema definitions

### Schema Validation (Optional)

Skills can optionally validate generated JSON:

```python
import jsonschema
import json

# Load schema
with open('.claude/skills/legacylift-classic/skills/fact-graph/templates/entity.schema.json') as f:
    schema = json.load(f)

# Validate entity
jsonschema.validate(entity, schema)
```

