# Fact Graph JSON Schema Templates

This directory contains JSON Schema definitions for the LegacyLift Fact Graph data model. These schemas define the structure and validation rules for the knowledge graph extracted from codebases.

## Overview

The fact graph represents codebase knowledge as a structured graph with four core data types:

1. **Entities** - Code elements (classes, functions, tables, services, etc.)
2. **Relations** - Relationships between entities (inherits, calls, uses, etc.)
3. **Facts** - Verifiable claims about entities with evidence
4. **Index** - Master metadata and pack references

## Schema Files

### 1. entity.schema.json

Defines the structure of an entity in the knowledge graph.

**Required Fields:**
- `id`: Unique deterministic identifier (content-based hash)
- `type`: Entity kind (class, function, table, endpoint, etc.)
- `name`: Simple name of the entity
- `file`: Relative path from repository root
- `line_range`: [start, end] line numbers (1-indexed, inclusive)

**Optional Fields:**
- `qualified_name`: Fully qualified name (namespace, schema, etc.)
- `attributes`: Type-specific metadata (language, visibility, columns, parameters, etc.)

**Example:**
```json
{
  "id": "class-userservice-a1b2c3",
  "type": "class",
  "name": "UserService",
  "qualified_name": "MyApp.Services.UserService",
  "file": "src/Services/UserService.cs",
  "line_range": [10, 150],
  "attributes": {
    "language": "csharp",
    "visibility": "public",
    "namespace": "MyApp.Services",
    "implements": ["IUserService"],
    "domain": "UserManagement",
    "technical_layer": "Service",
    "capability": "UserAuthentication",
    "content_hash": "a3b5c7d9e1f2"
  }
}
```

### 2. relation.schema.json

Defines a relationship between two entities.

**Required Fields:**
- `id`: Unique deterministic identifier
- `type`: Relationship kind (inherits, calls, uses, foreign_key, etc.)
- `source_id`: Entity ID of the source
- `target_id`: Entity ID of the target
- `file`: File where the relationship is expressed (relative path from repository root)
- `line`: Line number where relationship occurs (1-indexed)

**Optional Fields:**
- `attributes`: Relationship-specific metadata (cardinality, cascade, via, etc.)

**Examples:**

**Class Implementation:**
```json
{
  "id": "rel-implements-abc123",
  "type": "implements",
  "source_id": "cs:services-userservice-a1b2c3",
  "target_id": "cs:interfaces-iuserservice-x9y8z7",
  "file": "src/Services/UserService.cs",
  "line": 10,
  "attributes": {
    "via": "interface implementation"
  }
}
```

**Class Inheritance:**
```json
{
  "id": "rel-inherits-def456",
  "type": "inherits",
  "source_id": "cs:repositories-userrepository-b2c3d4",
  "target_id": "cs:repositories-baserepository-y8z9a0",
  "file": "src/Repositories/UserRepository.cs",
  "line": 15,
  "attributes": {
    "via": "class extension"
  }
}
```

**Method Call:**
```json
{
  "id": "rel-calls-ghi789",
  "type": "calls",
  "source_id": "cs:services-orderservice-c3d4e5",
  "target_id": "cs:services-emailservice-d4e5f6",
  "file": "src/Services/OrderService.cs",
  "line": 45,
  "attributes": {
    "via": "method invocation",
    "method_name": "SendConfirmation"
  }
}
```

**Foreign Key:**
```json
{
  "id": "rel-foreignkey-jkl012",
  "type": "foreign_key",
  "source_id": "db:orders-order-e5f6g7",
  "target_id": "db:users-user-f6g7h8",
  "file": "database/schema/orders.sql",
  "line": 12,
  "attributes": {
    "via": "foreign key constraint",
    "source_column": "user_id",
    "target_column": "id",
    "cascade": "delete"
  }
}
```

**Import/Dependency:**
```json
{
  "id": "rel-imports-mno345",
  "type": "imports",
  "source_id": "cs:controllers-ordercontroller-g7h8i9",
  "target_id": "cs:services-orderservice-c3d4e5",
  "file": "src/Controllers/OrderController.cs",
  "line": 5,
  "attributes": {
    "via": "import statement",
    "imported_class": "MyApp.Services.OrderService"
  }
}
```

**Note:** Relations use top-level `file` and `line` fields to indicate where the relationship is declared or expressed. This is distinct from facts, which use an `evidence` array with `line_range` to provide supporting evidence for claims.

### 3. fact.schema.json

Defines a verifiable fact about an entity, grounded in evidence.

**Required Fields:**
- `id`: Unique deterministic identifier
- `subject_id`: Entity ID the fact is about
- `predicate`: What is being asserted (has_property, validates, integrates_with, etc.)
- `object`: The value completing the fact (string, number, boolean, entity ID)
- `evidence`: Array of evidence with file paths and line ranges (must have at least one)

**Optional Fields:**
- `confidence`: Extraction confidence (high, medium, low) - defaults to high
- `attributes`: Fact-specific metadata (data_type, constraint_type, provider, etc.)

**Example:**
```json
{
  "id": "fact-userservice-integrates-azuread",
  "subject_id": "cs:services-userservice-a1b2c3",
  "predicate": "integrates_with",
  "object": "AzureAD",
  "evidence": [
    {
      "file": "src/Services/UserService.cs",
      "line_range": [45, 52],
      "snippet": "private readonly IAzureAdClient _azureAdClient;",
      "snippet_hash": "a1b2c3d4e5f6"
    }
  ],
  "confidence": {
    "score": 0.95,
    "reasoning": "Inferred from dependency injection of IAzureAdClient interface in constructor"
  },
  "attributes": {
    "provider": "Microsoft.Identity"
  }
}
```

### 4. index.schema.json

Defines the master index file structure.

**Required Fields:**
- `metadata`: Generation metadata (repository, generated_at, tool_version, analysis_scope, project_type, architecture_pattern)
- `statistics`: Counts and breakdowns (entity_count, relation_count, fact_count, files_analyzed, packs_metadata)
  - `packs_metadata`: Array of domain-scoped pack metadata with file paths, counts, and keywords
- `packs`: Note about domain-scoped packs (refers to packs_metadata)

**Optional Fields:**
- `schema_version`: Version of the fact graph schema (default: "1.0")

**Example:**
```json
{
  "metadata": {
    "repository": "trivia-manager",
    "generated_at": "2026-02-04T20:30:00Z",
    "tool_version": "1.0.0",
    "analysis_scope": "full",
    "project_type": "web_app",
    "architecture_pattern": "layered"
  },
  "statistics": {
    "entity_count": 247,
    "relation_count": 512,
    "fact_count": 834,
    "files_analyzed": 89,
    "entity_types": {
      "class": 42,
      "function": 156,
      "table": 12,
      "endpoint": 37
    },
    "relation_types": {
      "inherits": 63,
      "uses": 57,
      "implements": 19
    },
    "fact_predicates": {
      "has_method": 424,
      "has_property": 259,
      "returns": 307
    },
    "languages": {
      "csharp": 198,
      "sql": 12,
      "javascript": 37
    },
    "lines_of_code": {
      "total_loc": 14892,
      "total_files": 116,
      "by_language": {
        "C#":         { "files": 110, "blank": 450, "comment": 250, "code": 13800, "total": 14500, "percentage": 97.4 },
        "SQL":        { "files": 5,   "blank": 20,  "comment": 10,  "code": 220,   "total": 250,   "percentage": 1.7 },
        "JavaScript": { "files": 1,   "blank": 8,   "comment": 4,   "code": 130,   "total": 142,   "percentage": 0.9 }
      },
      "methodology": "cloc --vcs=git (total = blank + comment + code; git-tracked files only; legacylift* directories excluded)"
    },
    "packs_metadata": [
      {
        "packId": "pack:orders",
        "domain": "Orders",
        "files": {
          "entities": "packs/orders.entities.pack.json",
          "relations": "packs/orders.relations.pack.json",
          "facts": "packs/orders.facts.pack.json"
        },
        "entity_count": 145,
        "relation_count": 298,
        "fact_count": 476,
        "keywords": ["order", "item", "cart", "checkout", "payment"]
      },
      {
        "packId": "pack:users",
        "domain": "Users",
        "files": {
          "entities": "packs/users.entities.pack.json",
          "relations": "packs/users.relations.pack.json",
          "facts": "packs/users.facts.pack.json"
        },
        "entity_count": 67,
        "relation_count": 142,
        "fact_count": 218,
        "keywords": ["user", "auth", "profile", "account", "role"]
      },
      {
        "packId": "pack:core",
        "domain": "Core",
        "files": {
          "entities": "packs/core.entities.pack.json",
          "relations": "packs/core.relations.pack.json",
          "facts": "packs/core.facts.pack.json"
        },
        "entity_count": 35,
        "relation_count": 72,
        "fact_count": 140,
        "keywords": ["util", "helper", "common", "base", "abstract"]
      }
    ]
  },
  "packs": {
    "note": "This repository uses domain-scoped packs. See packs_metadata for details."
  },
  "schema_version": "1.0"
}
```

## Pack File Structure

Pack files are **domain-scoped** JSON files containing entities, relations, or facts for a specific business domain:

### Domain-Scoped Packs

Each domain has three pack files:
- `{domain}.entities.pack.json` - All entities for the domain
- `{domain}.relations.pack.json` - All relations for the domain
- `{domain}.facts.pack.json` - All facts for the domain

**Example:** For the "Orders" domain:

### orders.entities.pack.json
```json
{
  "schema": "https://legacylift.ai/schemas/entity.json",
  "packId": "pack:orders",
  "domain": "Orders",
  "entities": [
    { /* entity 1 */ },
    { /* entity 2 */ },
    ...
  ]
}
```

### orders.relations.pack.json
```json
{
  "schema": "https://legacylift.ai/schemas/relation.json",
  "packId": "pack:orders",
  "domain": "Orders",
  "relations": [
    { /* relation 1 */ },
    { /* relation 2 */ },
    ...
  ]
}
```

### orders.facts.pack.json
```json
{
  "schema": "https://legacylift.ai/schemas/fact.json",
  "packId": "pack:orders",
  "domain": "Orders",
  "facts": [
    { /* fact 1 */ },
    { /* fact 2 */ },
    ...
  ]
}
```

**Benefits of Domain-Scoped Packs:**
- Faster loading - skills can load only relevant domains
- Better organization - entities grouped by business capability
- Scalable - supports repositories with hundreds of domains
- Parallel generation - domains can be analyzed independently

## Using Lines of Code Metrics

The fact graph index includes comprehensive lines of code (LOC) statistics that other skills can consume to avoid redundant code analysis.

### Accessing LOC Metrics

```python
import json

# Load index
with open('legacylift-docs/context/index.json') as f:
    index = json.load(f)
    loc = index['statistics']['lines_of_code']

# Repository-level metrics
print(f"Total LOC: {loc['total_loc']:,}")
print(f"Total Files: {loc['total_files']}")

# Breakdown by language (cloc output)
for lang, stats in loc['by_language'].items():
    print(f"{lang}: {stats['code']:,} code lines ({stats['percentage']}%) in {stats['files']} files "
          f"[blank={stats['blank']}, comment={stats['comment']}, total={stats['total']}]")

# Output:
# Total LOC: 14,892
# Total Files: 116
# C#: 13,800 code lines (92.7%) in 110 files [blank=450, comment=250, total=14,500]
# SQL: 220 code lines (1.5%) in 5 files [blank=20, comment=10, total=250]
# JavaScript: 130 code lines (0.9%) in 1 file [blank=8, comment=4, total=142]
```

### LOC Methodology

**Counting Approach:**
- Uses `cloc --vcs=git` (honors `.gitignore` automatically)
- Distinguishes blank lines, comment lines, and source code lines per language
- `total` for each language = `blank + comment + code` (physical line count)
- `total_loc` = sum of all language `total` values

**Exclusions:**
- Git-ignored files excluded automatically via `--vcs=git`
- `legacylift*` directories excluded via `--not-match-d=legacylift`

**Why Total Lines?**
- Simple, deterministic, language-agnostic
- Matches industry-standard tools (cloc, tokei, etc.)
- Fast to compute
- Consistent across different codebases
- Good proxy for codebase size and complexity

### Entity-Level LOC

While repository-level LOC is stored in the index, entity-level LOC can be calculated from the `line_range` field:

```python
# Load entities
with open('legacylift-docs/context/packs/entities.pack.json') as f:
    entities = json.load(f)['entities']

# Calculate LOC for a specific entity
entity = next(e for e in entities if e['name'] == 'CreateQuestionEndpoint')
start, end = entity['line_range']
entity_loc = end - start + 1  # +1 because line_range is inclusive
print(f"{entity['name']}: {entity_loc} lines")

# Calculate average LOC per class
classes = [e for e in entities if e['type'] == 'class']
total_class_loc = sum(e['line_range'][1] - e['line_range'][0] + 1 for e in classes)
avg_loc = total_class_loc / len(classes) if classes else 0
print(f"Average class size: {avg_loc:.1f} lines")
```

### Consuming LOC in Other Skills

Other LegacyLift skills can consume LOC metrics from the fact graph instead of re-scanning the codebase:

```python
# In your skill's Phase 1 (Discovery)
import os
import json

# Check if fact graph exists
fact_graph_path = 'legacylift-docs/context/index.json'
if os.path.exists(fact_graph_path):
    # Load LOC from fact graph
    with open(fact_graph_path) as f:
        index = json.load(f)
        loc_metrics = index['statistics']['lines_of_code']

    # Use pre-computed metrics
    total_loc = loc_metrics['total_loc']
    by_language = loc_metrics['by_language']
else:
    # Fallback: Count LOC manually
    # (use find + wc -l commands)
    pass
```

**Benefits:**
- ✅ **Faster**: No need to re-scan filesystem
- ✅ **Consistent**: All skills use same LOC values
- ✅ **Efficient**: Avoids redundant `find` + `wc` operations
- ✅ **Single Source**: Fact graph as canonical data source

### Example: exec-summary-generator Integration

The `exec-summary-generator` skill can consume LOC from the fact graph:

```markdown
<!-- In 00-EXECUTIVE-SUMMARY.md -->
## Codebase Metrics

**Total Lines of Code: 14,892**

Across **116 files**

### Breakdown by File Type:
| File Type | Lines of Code | Number of Files | Percentage |
|-----------|--------------|-----------------|------------|
| .cs       | 14,500       | 110            | 97.4%      |
| .sql      | 250          | 5              | 1.7%       |
| .js       | 142          | 1              | 0.9%       |
```

The skill simply reads from `index.json` instead of running `find` + `wc` commands, making documentation generation faster and ensuring consistency across all documentation.

## Enhanced Fact Types (NEW)

The fact graph now includes 7 enhanced capabilities to provide richer semantic information for documentation skills.

### 1. Workflow & State Machine Facts

Captures business process flows and state transitions.

**New Fact Types:**
- `state_transition`: Documents state changes (e.g., "Pending → Approved")
- `process_step`: Documents steps in a workflow or business process

**Example:**
```json
{
  "id": "fact-orderservice-state-transition-xyz",
  "subject_id": "cs:services-orderservice-abc123",
  "predicate": "state_transition",
  "object": "Pending→Approved",
  "evidence": [
    {
      "file": "src/Services/OrderService.cs",
      "line_range": [45, 52],
      "snippet": "if (paymentVerified) { order.Status = OrderStatus.Approved; }",
      "snippet_hash": "b2c3d4e5f6a1"
    }
  ],
  "confidence": {
    "score": 0.9,
    "reasoning": "Extracted from explicit Status property assignment within conditional logic"
  },
  "attributes": {
    "from_state": "Pending",
    "to_state": "Approved",
    "condition": "payment verified"
  }
}
```

**Use Cases:**
- Business process documentation
- Workflow visualization
- State machine diagrams
- Business rule extraction

### 2. HTTP Endpoint Metadata Facts

Provides structured API documentation with request/response details.

**New Fact Types:**
- `http_method`: HTTP method (GET, POST, PUT, DELETE, PATCH)
- `accepts_param`: Parameter accepted by endpoint
- `returns_response`: Response type returned by endpoint
- `requires_auth`: Authentication requirement

**Example:**
```json
{
  "id": "fact-createorderendpoint-http-method-xyz",
  "subject_id": "ep:orders-createorderendpoint-abc123",
  "predicate": "http_method",
  "object": "POST",
  "evidence": [
    {
      "file": "src/Endpoints/CreateOrderEndpoint.cs",
      "line_range": [26, 26],
      "snippet": "Post(\"/api/orders\");",
      "snippet_hash": "c3d4e5f6a1b2"
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
    "response_dto": "OrderDto"
  }
}
```

**Use Cases:**
- API documentation generation
- System integration guides
- OpenAPI/Swagger spec generation
- API testing

### 3. Domain/Layer Classification

Organizes entities by **business domain** (what) and **technical layer** (how), supporting both domain-driven and architecture-focused analysis.

**New Entity Attributes:**
- `domain`: **Business domain** - the business capability this entity supports (e.g., "Orders", "UserManagement", "Billing", "Core")
- `technical_layer`: **Technical architecture layer** - how the entity is organized (e.g., "Model", "Service", "Persistence", "Web", "Util")
- `capability`: Specific functional capability within the domain (e.g., "OrderProcessing", "PaymentHandling")

**Example:**
```json
{
  "id": "cs:orders-orderservice-abc123",
  "type": "class",
  "name": "OrderService",
  "qualified_name": "MyApp.Services.Orders.OrderService",
  "file": "src/Services/Orders/OrderService.cs",
  "line_range": [10, 150],
  "attributes": {
    "language": "csharp",
    "visibility": "public",
    "namespace": "MyApp.Services.Orders",
    "domain": "Orders",
    "technical_layer": "Service",
    "capability": "OrderProcessing"
  }
}
```

**Classification Heuristics:**

*Business Domain (Primary Axis):*
- Database table prefixes (e.g., `ORD_* tables → Orders domain`)
- Namespace domain segments (e.g., `MyApp.Services.Orders.* → Orders`)
- Folder structure (e.g., `src/orders/* → Orders`)
- Fallback: "Core" for truly cross-cutting utilities

*Technical Layer (Secondary Axis):*
- Package/namespace segments (e.g., `.service.* → Service`, `.persistence.* → Persistence`)
- Class name suffixes (e.g., `*Dao → Persistence`, `*Controller → Web`)
- Folder names (e.g., `/model/* → Model`, `/web/* → Web`)

**Use Cases:**
- **Domain-focused**: Group all Orders entities (model + service + persistence + web) together
- **Layer-focused**: Filter to show only Service layer across all domains
- **Cross-cutting**: Identify Core utilities vs domain-specific utilities
- Domain-driven design analysis
- Microservices boundary identification
- Layered architecture validation

### 4. Relationship Cardinality Facts

Documents the multiplicity of relationships between entities.

**New Fact Type:**
- `has_cardinality`: Relationship cardinality (one-to-one, one-to-many, many-to-one, many-to-many)

**Example:**
```json
{
  "id": "fact-order-orderitems-cardinality-xyz",
  "subject_id": "rel-has-member-abc123",
  "predicate": "has_cardinality",
  "object": "one-to-many",
  "evidence": [
    {
      "file": "src/Models/Order.cs",
      "line_range": [25, 25],
      "snippet": "public ICollection<OrderItem> Items { get; set; }",
      "snippet_hash": "d4e5f6a1b2c3"
    }
  ],
  "confidence": {
    "score": 0.95,
    "reasoning": "Inferred from ICollection<OrderItem> navigation property, standard Entity Framework pattern"
  },
  "attributes": {
    "orm_annotation": "@OneToMany"
  }
}
```

**Extraction Sources:**
- ORM annotations (`@OneToMany`, `@ManyToOne`, `@ManyToMany`, `@OneToOne`)
- Entity Framework fluent API
- JPA annotations
- Collection types (ICollection, List, Set)

**Use Cases:**
- ERD diagram generation
- Data model documentation
- Migration planning
- Database design validation

### 5. Business Rule Facts

Captures complex business logic and conditional rules.

**New Fact Type:**
- `business_rule`: Complex business rule or conditional logic beyond simple constraints

**Example:**
```json
{
  "id": "fact-orderservice-business-rule-xyz",
  "subject_id": "cs:services-orderservice-abc123",
  "predicate": "business_rule",
  "object": "Orders over $1000 require manager approval",
  "evidence": [
    {
      "file": "src/Services/OrderService.cs",
      "line_range": [78, 85],
      "snippet": "if (order.TotalAmount > 1000) { await RequireManagerApproval(order); }",
      "snippet_hash": "e5f6a1b2c3d4"
    }
  ],
  "confidence": {
    "score": 0.85,
    "reasoning": "Inferred from conditional logic checking TotalAmount > 1000 with approval requirement"
  },
  "attributes": {
    "rule_type": "approval",
    "threshold": 1000,
    "currency": "USD"
  }
}
```

**Extraction Patterns:**
- Conditional logic with thresholds (if amount > 1000)
- Approval workflows
- Calculation rules
- Discount logic
- Access control rules

**Use Cases:**
- Business requirements documentation
- Functional specification extraction
- Use case derivation
- Modernization planning

### 6. Content Hash for Drift Detection

Enables detection of code changes since fact graph generation.

**New Entity Attribute:**
- `content_hash`: SHA-256 hash (first 12 characters) of entity code block

**Example:**
```json
{
  "id": "class-orderservice-abc123",
  "type": "class",
  "name": "OrderService",
  "file": "src/Services/OrderService.cs",
  "line_range": [10, 150],
  "attributes": {
    "language": "csharp",
    "content_hash": "a3b5c7d9e1f2"
  }
}
```

**Calculation:**
```python
import hashlib

def calculate_content_hash(file_path: str, start_line: int, end_line: int) -> str:
    """Calculate SHA-256 hash of entity code block"""
    with open(file_path, 'r') as f:
        lines = f.readlines()
    content = ''.join(lines[start_line-1:end_line])
    hash_digest = hashlib.sha256(content.encode()).hexdigest()[:12]
    return hash_digest
```

**Use Cases:**
- Citation drift detection
- Documentation staleness alerts
- Code change tracking
- Documentation refresh triggers

### 7. Project Classification

Automatically classifies the project type and architecture pattern.

**New Metadata Fields:**
- `project_type`: Type of project (monolith, microservices, monorepo, library, cli_tool, web_app, mobile_app)
- `architecture_pattern`: Architecture pattern (layered, mvc, mvvm, clean, microservices, serverless, event_driven, cqrs)

**Example:**
```json
{
  "metadata": {
    "repository": "trivia-manager",
    "generated_at": "2026-02-04T20:30:00Z",
    "tool_version": "1.0.0",
    "analysis_scope": "full",
    "project_type": "microservices",
    "architecture_pattern": "layered"
  }
}
```

**Classification Heuristics:**

**Project Type Detection:**
- `microservices`: Multiple service directories + Docker/Kubernetes
- `monorepo`: Multiple related projects in one repository
- `library`: Package definition files (setup.py, package.json) without app entry points
- `cli_tool`: Command-line entry points (Main, Program, CLI classes)
- `web_app`: Web controllers, endpoints, or UI components
- `monolith`: Single cohesive application

**Architecture Pattern Detection:**
- `mvc`: Controllers + Models + Views
- `layered`: Presentation/Business/Data layer namespaces
- `clean`: Core/Domain + Application + Infrastructure layers
- `cqrs`: Commands + Queries + Handlers
- `microservices`: Multiple independent services

**Use Cases:**
- Executive summary generation
- Technology stack overview
- Architecture documentation
- Modernization strategy planning

## Validation

To validate generated JSON against these schemas, use a JSON Schema validator:

### Python Example
```python
import json
import jsonschema

# Load schema
with open('entity.schema.json') as f:
    entity_schema = json.load(f)

# Load data
with open('../../trivia-manager/legacylift-docs/context/packs/entities.pack.json') as f:
    entities_pack = json.load(f)

# Validate each entity
for entity in entities_pack['entities']:
    jsonschema.validate(entity, entity_schema)
    print(f"✓ {entity['name']} is valid")
```

### Node.js Example
```javascript
const Ajv = require('ajv');
const fs = require('fs');

const ajv = new Ajv();
const schema = JSON.parse(fs.readFileSync('entity.schema.json'));
const validate = ajv.compile(schema);

const entities = JSON.parse(fs.readFileSync('../../trivia-manager/legacylift-docs/context/packs/entities.pack.json'));

for (const entity of entities.entities) {
  const valid = validate(entity);
  if (valid) {
    console.log(`✓ ${entity.name} is valid`);
  } else {
    console.error(`✗ ${entity.name} is invalid:`, validate.errors);
  }
}
```

## Deterministic ID Generation

Entity, relation, and fact IDs must be deterministic (repeatable across runs). Use content-based hashing:

### Python Example
```python
import hashlib
import json

def generate_entity_id(entity_type: str, qualified_name: str, file: str) -> str:
    """Generate a deterministic entity ID"""
    content = f"{entity_type}:{qualified_name}:{file}"
    hash_digest = hashlib.sha256(content.encode()).hexdigest()[:12]
    return f"{entity_type}-{qualified_name.lower().replace('.', '-')}-{hash_digest}"

# Example
entity_id = generate_entity_id("class", "MyApp.Services.UserService", "src/Services/UserService.cs")
# Result: "class-myapp-services-userservice-a1b2c3d4e5f6"
```

## Entity Type Reference

### Application Code
- `class`: Class definition
- `interface`: Interface definition
- `function`: Function or method
- `method`: Class method (alternative to function)
- `enum`: Enumeration type
- `dto`: Data Transfer Object
- `model`: Domain model
- `service`: Service class
- `repository`: Repository class
- `controller`: API controller
- `endpoint`: API endpoint
- `middleware`: Middleware component
- `component`: UI component
- `module`: Module or package
- `config`: Configuration

### Database Objects
- `table`: Database table
- `view`: Database view
- `stored_proc`: Stored procedure
- `sql_function`: SQL function
- `trigger`: Database trigger
- `index`: Database index
- `constraint`: Database constraint

## Relation Type Reference

### Code Dependencies
- `inherits`: Class inheritance
- `implements`: Interface implementation
- `extends`: Class extension
- `uses`: General usage dependency
- `calls`: Function/method invocation
- `invokes`: Method invocation
- `references`: Property/field reference
- `imports`: Module import
- `depends_on`: Dependency

### Structure
- `contains`: Containment (class contains method)
- `owns`: Ownership
- `has_member`: Membership

### Data Access
- `reads_from`: Data reading
- `writes_to`: Data writing
- `queries`: Database query

### Database
- `foreign_key`: Foreign key relationship
- `join`: Table join

### Metadata
- `triggers`: Trigger activation
- `decorates`: Decorator/attribute
- `annotates`: Annotation
- `routes_to`: Routing

## Fact Predicate Reference

### Structure
- `has_property`: Entity has a property
- `has_attribute`: Entity has an attribute
- `has_method`: Entity has a method
- `has_field`: Entity has a field
- `has_column`: Table has a column

### Validation
- `validates`: Validation rule
- `requires`: Requirement constraint
- `ensures`: Postcondition
- `max_length`: Maximum length constraint
- `min_value`: Minimum value constraint
- `max_value`: Maximum value constraint
- `pattern_matches`: Regular expression pattern
- `is_required`: Field is required
- `is_nullable`: Field is nullable
- `is_unique`: Field must be unique
- `is_indexed`: Field is indexed

### Behavior
- `throws`: Exception throwing
- `returns`: Return value
- `accepts`: Parameter acceptance

### Integration
- `integrates_with`: External integration
- `authenticates_via`: Authentication method
- `authorizes_via`: Authorization method

### Data Operations
- `stores_in`: Storage location
- `reads_from`: Data source
- `writes_to`: Data destination
- `caches_in`: Caching mechanism
- `logs_to`: Logging destination
- `publishes_to`: Event publishing
- `subscribes_to`: Event subscription

### Configuration
- `triggers_on`: Trigger condition
- `schedules_at`: Scheduling
- `retries_on`: Retry behavior
- `timeout_after`: Timeout configuration
- `default_value`: Default value

### Workflow & State Machines (NEW)
- `state_transition`: State change (from state A to state B)
- `process_step`: Step in a workflow or business process

### HTTP Endpoint Metadata (NEW)
- `http_method`: HTTP method (GET, POST, PUT, DELETE, etc.)
- `accepts_param`: Endpoint accepts a parameter
- `returns_response`: Endpoint returns a response type
- `requires_auth`: Endpoint requires authentication

### Relationship Metadata (NEW)
- `has_cardinality`: Relationship cardinality (one-to-many, many-to-many, etc.)

### Business Rules (NEW)
- `business_rule`: Complex business rule or conditional logic

## Best Practices

### 1. Determinism
- Always use content-based hashing for IDs
- Sort all arrays before serialization
- Use consistent naming conventions
- Avoid timestamps in IDs

### 2. Evidence Quality
- Every fact must have at least one evidence entry
- Evidence line ranges should be tight (5-10 lines context)
- Include code snippets for human readability
- Verify file paths are correct and relative to repo root

### 3. Completeness
- Extract ALL entities in the analyzed scope
- Don't skip entities because they seem unimportant
- Include both application code and database objects
- Extract configuration and infrastructure code

### 4. Accuracy
- Never guess - only extract what's explicitly in code
- Use regex/AST parsing, not semantic interpretation
- Validate entity IDs are unique
- Ensure relation source/target IDs exist

### 5. Consistency
- Use consistent casing (lowercase IDs, PascalCase names)
- Follow language-specific conventions (namespace vs package vs schema)
- Maintain consistent attribute naming across entity types

---

*Generated By LegacyLift AI by CapTech*