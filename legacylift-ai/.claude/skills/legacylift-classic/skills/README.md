# LegacyLift Documentation Skills

> **Automated documentation generation and validation for legacy codebases**

## Overview

LegacyLift provides a suite of 18 skills for generating, validating, enhancing, and exporting documentation from source code. The workflow follows a **generate → validate → polish → export** pipeline to ensure high-quality, accurate documentation.

**⭐ New: Fact-Graph Integration (Feb 2026)** - All 13 documentation skills now automatically integrate with the `/legacylift-classic:fact-graph` skill for improved performance and consistent entity identification. The fact-graph creates a structured JSON knowledge base that eliminates redundant code analysis across skills.

---

## Important: Model Configuration for Large Documentation

Due to the comprehensive nature of the generated documentation files, it's essential to configure Claude Code for optimal performance:

### Step 1: Maximize Context Window

Before running documentation generation skills, set the model to use an extended context window:

```bash
/model sonnet[1m]
```

This configures the model to use approximately 1 million tokens of context, which is necessary for generating large, comprehensive documentation files.

### Step 2: Context Management Instructions

**Note**: As of the latest update, all documentation generation skills include built-in persistence and autonomy guidelines. However, if you find the built-in context management isn't working as expected, you can explicitly append the following instruction to your prompt as a fallback:

```
Your context window will be automatically compacted as it approaches its limit, allowing you to continue working indefinitely from where you left off. Therefore, do not stop tasks early due to token budget concerns. As you approach your token budget limit, save your current progress and state to memory before the context window refreshes. Always be as persistent and autonomous as possible and complete tasks fully, even if the end of your budget is approaching. Never artificially stop any task early regardless of the context remaining.
```

### Example Usage

```bash
# Configure model first
/model sonnet[1m]

# Then run skills with context management instructions
/legacylift-classic:exec-summary-generator code_path=repos/my_project

Your context window will be automatically compacted as it approaches its limit, allowing you to continue working indefinitely from where you left off. Therefore, do not stop tasks early due to token budget concerns. As you approach your token budget limit, save your current progress and state to memory before the context window refreshes. Always be as persistent and autonomous as possible and complete tasks fully, even if the end of your budget is approaching. Never artificially stop any task early regardless of the context remaining.
```

### Why This Matters

- **Large Output Files**: Documentation files (especially comprehensive reports and detailed requirements) can exceed 5,000+ lines
- **Multiple Documents**: Running multiple skills generates 6 core documents (00-05) plus additional domain-specific documents
- **Domain-Specific Variants**: Skills like `/legacylift-classic:database-layer-documenter` and `/legacylift-classic:use-case-generator` may generate multiple domain-specific files
- **Thorough Analysis**: Complete code analysis requires maintaining large amounts of context about the codebase structure

**Note**: Without proper configuration, documentation generation may be incomplete or truncated. Always follow these steps before running documentation generation skills.

---

## Skills Inventory

| # | Skill | Type | Output |
|---|-------|------|--------|
| 1 | `/legacylift-classic:fact-graph` | **Foundation** | **JSON knowledge graph (context/)** |
| 2 | `/legacylift-classic:exec-summary-generator` | Generator | 00-EXECUTIVE-SUMMARY.md |
| 3 | `/legacylift-classic:si-documenter` | Generator | 01-SYSTEM-ARCHITECTURE.md, 04-INTEGRATION-AND-API-GUIDE.md |
| 4 | `/legacylift-classic:data-documenter` | Generator | 02-DATA-MODEL-AND-RELATIONSHIPS.md |
| 5 | `/legacylift-classic:database-layer-documenter` | Generator | 02-DATA-MODEL-AND-RELATIONSHIPS-{DOMAIN}.md |
| 6 | `/legacylift-classic:data-dictionary-generator` | Generator | 12-DATA-DICTIONARY-{DOMAIN}.md |
| 7 | `/legacylift-classic:business-documenter` | Generator | 03-BUSINESS-RULES-AND-REQUIREMENTS.md |
| 8 | `/legacylift-classic:detailed-req-documenter` | Generator | 03-BUSINESS-RULES-AND-REQUIREMENTS-{CORE}.md |
| 9 | `/legacylift-classic:use-case-generator` | Generator | 08-USE-CASES-{DOMAIN}.md |
| 10 | `/legacylift-classic:user-story-generator` | Generator | 11-USER-STORIES-{DOMAIN}.md |
| 11 | `/legacylift-classic:table-validation` | Validator | 06-TABLE-VALIDATION-*.md (3 reports) |
| 12 | `/legacylift-classic:gap-analyzer` | Analyzer | 10-GAP-ANALYSIS-REPORT.md |
| 13 | `/legacylift-classic:documentation-review` | Validator | 07-DOCUMENTATION-ACCURACY-REPORT.md |
| 14 | `/legacylift-classic:citation-validator` | Validator | 09-CITATION-VALIDATION-REPORT.md |
| 15 | `/legacylift-classic:table-of-definitions` | Enhancer | Appends Table of Definitions to existing `.md` files |
| 16 | `/legacylift-classic:doc-exporter` | Exporter | Word (.docx) or PDF (.pdf) with rendered Mermaid diagrams |
| 17 | `/legacylift-classic:repo-summary-generator` | Summarizer | Comprehensive summary with metrics and statistics |
| 18 | `/legacylift-classic:cloc` | Utility | `legacylift-docs/cloc-report.txt` or `cloc-report.json` (when `save=true`; otherwise display only) |

**⚠️ Important**: Run `/legacylift-classic:fact-graph` first before other skills for optimal performance. All skills (2-17) automatically detect and use the fact-graph when available.

---

## Workflow Diagram

> Skill names are drawn **without** the `legacylift-classic:` prefix in the boxed diagrams below, purely so the boxes stay aligned. The real invocation is always `/legacylift-classic:<name>` — as shown in every command block and table in this document.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DOCUMENTATION WORKFLOW                          │
└─────────────────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────────────┐
  │        PHASE 0: FOUNDATION (Optional but Recommended)            │
  │                                                                  │
  │   ┌─────────────────┐    Creates knowledge graph                 │
  │   │  /fact-graph    │ ─► for improved performance                │
  │   └─────────────────┘    (JSON: entities, relations, facts)      │
  │                                                                  │
  │   ✅ Run once, benefits all subsequent skills                     │
  │   ✅ Eliminates redundant grep/read operations                    │
  │   ✅ O(1) lookups instead of O(N) searches                        │
  │                                                                  │
  └──────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │                    PHASE 1: GENERATION                           │
  │                                                                  │
  │   Run generators in sequence with dependencies shown:            │
  │                                                                  │
  │   1️⃣ FIRST: Executive Summary (foundation for all)               │
  │      ┌─────────────────────┐                                     │
  │      │/exec-summary-generator│─► 00-EXECUTIVE-SUMMARY.md         │
  │      └─────────────────────┘                                     │
  │                                                                  │
  │   2️⃣ THEN: Core Documenters (can run in parallel)                │
  │                                                                  │
  │      ┌─────────────────────┐                                     │
  │      │  /si-documenter     │─► 01-SYSTEM-ARCHITECTURE.md         │
  │      │                     │   04-INTEGRATION-AND-API-GUIDE.md   │
  │      │                     │   05-QUICK-REFERENCE.md             │
  │      └─────────────────────┘                                     │
  │                                                                  │
  │      ┌─────────────────────┐     ┌────────────────────┐          │
  │      │ /data-documenter    │────►│/database-layer-    │          │
  │      │ (02-DATA-MODEL...)  │     │ documenter         │          │
  │      └─────────────────────┘     │(02-DATA-MODEL-     │          │
  │                │                 │ {DOMAIN}.md)       │          │
  │                │                 └────────────────────┘          │
  │                │                                                 │
  │                └────────────────►┌────────────────────┐          │
  │                                  │/data-dictionary-   │          │
  │                                  │ generator          │          │
  │                                  │(12-DATA-DICTIONARY-│          │
  │                                  │ {DOMAIN}.md)       │          │
  │                                  └────────────────────┘          │
  │                                                                  │
  │      ┌─────────────────────┐     ┌────────────────────┐          │
  │      │/business-documenter │────►│/detailed-req-      │          │
  │      │(03-BUSINESS-RULES...)│     │ documenter         │──┐       │
  │      └─────────────────────┘     │(03-BUSINESS-RULES- │  │       │
  │                                  │ {CORE}.md)         │  │       │
  │                                  └────────────────────┘  │       │
  │                                           │              │       │
  │                                           ▼              │       │
  │                                  ┌────────────────────┐  │       │
  │                                  │/use-case-generator │  │       │
  │                                  │(08-USE-CASES-      │  │       │
  │                                  │ {DOMAIN}.md)       │  │       │
  │                                  └────────────────────┘  │       │
  │                                           │              │       │
  │                                           ▼              │       │
  │                                  ┌────────────────────┐  │       │
  │                                  │/user-story-        │  │       │
  │                                  │ generator          │  │       │
  │                                  │(11-USER-STORIES-   │  │       │
  │                                  │ {DOMAIN}.md)       │  │       │
  │                                  └────────────────────┘  │       │
  │                                                          │       │
  │   ✅ All auto-detect and use fact-graph when available    │       │
  │                                                          │       │
  └──────────────────────────────────────────────────────────┼───────┘
                                  │                          │
                                  ▼                          │
  ┌──────────────────────────────────────────────────────────┼───────┐
  │                    PHASE 2: VALIDATION                   │       │
  │                                                          │       │
  │   Run validators to ensure accuracy and integrity:       │       │
  │                                                          │       │
  │   ┌────────────────────┐   Validates ORM mappings vs    │       │
  │   │ /table-validation  │─► SQL DDL schema               │       │
  │   └────────────────────┘   (06-TABLE-VALIDATION-*.md)   │       │
  │            │                                             │       │
  │            ▼                                             │       │
  │   ┌─────────────────────┐    Validates file:line        │       │
  │   │ /citation-validator │ ─► citations                  │       │
  │   └─────────────────────┘    (09-CITATION-VALIDATION... )│       │
  │            +                                             │       │
  │   ┌──────────────────────┐   Validates technical claims │       │
  │   │ /documentation-review│ ─► (semantic accuracy)       │       │
  │   └──────────────────────┘   (07-DOCUMENTATION-ACCURACY...)│     │
  │                                                          │       │
  └──────────────────────────────────────────────────────────┼───────┘
                                  │                          │
                                  ▼                          │
  ┌──────────────────────────────────────────────────────────┼───────┐
  │                    PHASE 3: ANALYSIS                     │       │
  │                                                          │       │
  │   ┌─────────────────┐                                    │       │
  │   │  /gap-analyzer  │ ─► Identifies missing documentation│       │
  │   └─────────────────┘    (10-GAP-ANALYSIS-REPORT.md)    │       │
  │                          (uses fact-graph for complete   │       │
  │                           inventory)                     │       │
  │                                                          │       │
  └──────────────────────────────────────────────────────────┼───────┘
                                  │                          │
                                  ▼                          │
                        ┌─────────────────┐
                        │ Issues Found?   │
                        └────────┬────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                   YES                        NO
                    │                         │
                    ▼                         ▼
  ┌──────────────────────────────┐    ┌─────────────────┐
  │    PHASE 4: FIX ISSUES       │    │     DONE!       │
  │                              │    │                 │
  │ Review accuracy report and   │    │                 │
  │ manually fix identified      │    │                 │
  │ issues in documentation      │    │                 │
  │                              │    │                 │
  │ Or regenerate problematic    │    │                 │
  │ sections with skills         │    │                 │
  └──────────────────────────────┘    │                 │
                    │                 │                 │
                    │ Re-run          │                 │
                    │ validators      │                 │
                    └──────────►      │                 │
                  (back to Phase 2)   │                 │
                                      └────────┬────────┘
                                               │
                                               ▼
  ┌──────────────────────────────────────────────────────┐
  │              PHASE 5: POLISH (Optional)               │
  │                                                       │
  │   ┌──────────────────────────┐                        │
  │   │ /table-of-definitions    │ ─► Adds glossary &     │
  │   └──────────────────────────┘    ToC link to each    │
  │                                   document            │
  │                                                       │
  │   ┌──────────────────────────┐                        │
  │   │ /repo-summary-generator  │ ─► Metrics, stats,     │
  │   └──────────────────────────┘    facts at a glance   │
  │                                                       │
  └──────────────────────────────────────────────────────┘
                                  │
                                  ▼
  ┌──────────────────────────────────────────────────────┐
  │              PHASE 6: EXPORT (Optional)               │
  │                                                       │
  │   ┌──────────────────────────┐                        │
  │   │ /doc-exporter            │ ─► Word (.docx) or     │
  │   └──────────────────────────┘    PDF (.pdf) with     │
  │                                   rendered mermaid    │
  │                                   diagrams & CapTech  │
  │                                   branding            │
  └──────────────────────────────────────────────────────┘
```

---

## The Fact-Graph: Foundation for All Documentation

### What is the Fact-Graph?

The **fact-graph** is a structured JSON knowledge graph that serves as a **single source of truth** for all code analysis in LegacyLift. It systematically extracts and indexes all entities (classes, functions, tables, endpoints, etc.), their relationships, and facts about them from your codebase, creating a comprehensive, queryable representation of your code.

Think of it as a **pre-indexed catalog** of your entire codebase that all other skills can instantly query instead of repeatedly grepping and reading files.

### Why Use Fact-Graph?

**Without fact-graph:** Each skill independently greps, searches, and analyzes the same codebase, resulting in:
- Redundant code analysis (same files read multiple times)
- Slower execution (grep operations are expensive)
- Potential inconsistencies (different skills might identify entities differently)

**With fact-graph:** Run fact-graph once, then all other skills consume its output, resulting in:
- ✅ **Improved documentation generation performance** (eliminates redundant grep/read operations)
- ✅ **Consistent entity identification** across all documentation
- ✅ **O(1) dictionary lookups** instead of O(N) grep searches
- ✅ **Evidence-based citations** (every entity has file:line references)
- ✅ **Deterministic output** (same codebase → same entities every time)

### When to Use Fact-Graph

**Always run fact-graph first** when:
- Generating documentation for a new codebase
- The codebase has changed significantly since last documentation
- You want maximum performance for multi-skill runs

**You can skip fact-graph** when:
- Running a single quick skill on a small codebase
- The fact-graph already exists and the code hasn't changed

### How to Use Fact-Graph

```bash
# Step 1: Configure model
/model sonnet[1m]

# Step 2: Generate fact-graph (one-time setup per codebase)
/legacylift-classic:fact-graph code_path=repos/my_project

# Output: Creates legacylift-docs/context/ directory with:
# - index.json (metadata and statistics)
# - packs/{domain}.entities.pack.json (all code entities by domain)
# - packs/{domain}.relations.pack.json (entity relationships by domain)
# - packs/{domain}.facts.pack.json (facts about entities by domain)

# Step 3: Run any documentation skills - they auto-detect and use fact-graph
/legacylift-classic:exec-summary-generator code_path=repos/my_project
# ✅ Uses fact-graph automatically for fast entity lookups

/legacylift-classic:business-documenter code_path=repos/my_project
# ✅ Uses fact-graph for validation rules, business logic

/legacylift-classic:use-case-generator domain=Orders code_path=repos/my_project
# ✅ Uses fact-graph for endpoints, controllers, services
```

### Fact-Graph Structure

The fact-graph generates a `legacylift-docs/context/` directory with domain-scoped pack files:

```
repos/my_project/
└── legacylift-docs/
    └── context/
        ├── index.json                      # Metadata and statistics
        └── packs/
            ├── core.entities.pack.json     # Core domain entities
            ├── core.relations.pack.json    # Core domain relations
            ├── core.facts.pack.json        # Core domain facts
            ├── orders.entities.pack.json   # Orders domain entities
            ├── orders.relations.pack.json  # Orders domain relations
            └── orders.facts.pack.json      # Orders domain facts
```

#### 1. index.json - Repository Metadata

Contains high-level statistics and metadata:

```json
{
  "metadata": {
    "repository": "my_project",
    "analyzed_at": "2026-02-06T10:30:00Z",
    "project_type": "monolith",
    "architecture_pattern": "layered",
    "primary_language": "csharp"
  },
  "statistics": {
    "lines_of_code": {
      "total_loc": 125000,
      "by_extension": {
        "cs": 95000,
        "sql": 15000,
        "js": 10000,
        "json": 5000
      }
    },
    "entity_types": {
      "class": 450,
      "interface": 80,
      "method": 3200,
      "function": 120,
      "endpoint": 85,
      "table": 65,
      "stored_proc": 45
    },
    "languages": {
      "C#": 76.0,
      "SQL": 12.0,
      "JavaScript": 8.0,
      "JSON": 4.0
    },
    "packs_metadata": [
      {
        "domain": "core",
        "entity_count": 520,
        "relation_count": 1850,
        "fact_count": 2400
      },
      {
        "domain": "orders",
        "entity_count": 180,
        "relation_count": 620,
        "fact_count": 890
      }
    ]
  }
}
```

#### 2. entities.pack.json - Code Entities

Each domain pack contains all entities in that domain:

```json
{
  "domain": "orders",
  "entity_count": 180,
  "entities": [
    {
      "id": "class-order-abc123",
      "type": "class",
      "name": "Order",
      "file": "src/Orders/Models/Order.cs",
      "line_range": [15, 85],
      "attributes": {
        "namespace": "MyProject.Orders.Models",
        "visibility": "public",
        "is_abstract": false,
        "domain": "Orders",
        "annotations": ["Entity", "Table(\"Orders\")"]
      }
    },
    {
      "id": "endpoint-createorder-xyz789",
      "type": "endpoint",
      "name": "CreateOrder",
      "file": "src/Orders/Controllers/OrderController.cs",
      "line_range": [45, 62],
      "attributes": {
        "http_method": "POST",
        "route": "/api/orders",
        "namespace": "MyProject.Orders.Controllers",
        "domain": "Orders"
      }
    },
    {
      "id": "table-orders-def456",
      "type": "table",
      "name": "Orders",
      "file": "database/schema/orders.sql",
      "line_range": [10, 45],
      "attributes": {
        "schema": "dbo",
        "domain": "Orders"
      }
    }
  ]
}
```

#### 3. relations.pack.json - Entity Relationships

Captures relationships between entities:

```json
{
  "domain": "orders",
  "relation_count": 620,
  "relations": [
    {
      "id": "relation-abc-xyz",
      "type": "calls",
      "source_id": "endpoint-createorder-xyz789",
      "target_id": "method-createorder-service-123",
      "evidence": [
        {
          "file": "src/Orders/Controllers/OrderController.cs",
          "line_range": [50, 52]
        }
      ]
    },
    {
      "id": "relation-order-orderitem-fk",
      "type": "foreign_key",
      "source_id": "table-orderitems-ghi789",
      "target_id": "table-orders-def456",
      "evidence": [
        {
          "file": "database/schema/order_items.sql",
          "line_range": [25, 27]
        }
      ],
      "attributes": {
        "foreign_key_name": "FK_OrderItems_Orders",
        "source_column": "OrderId",
        "target_column": "Id"
      }
    }
  ]
}
```

#### 4. facts.pack.json - Facts About Entities

Contains properties, validations, business rules, and other facts:

```json
{
  "domain": "orders",
  "fact_count": 890,
  "facts": [
    {
      "id": "fact-order-property-total",
      "subject_id": "class-order-abc123",
      "predicate": "has_property",
      "object": "TotalAmount",
      "evidence": [
        {
          "file": "src/Orders/Models/Order.cs",
          "line_range": [35, 36]
        }
      ],
      "attributes": {
        "data_type": "decimal",
        "visibility": "public"
      }
    },
    {
      "id": "fact-order-validation-required",
      "subject_id": "class-order-abc123",
      "predicate": "is_required",
      "object": "CustomerId",
      "evidence": [
        {
          "file": "src/Orders/Validators/OrderValidator.cs",
          "line_range": [18, 20]
        }
      ],
      "attributes": {
        "validation_type": "Required",
        "error_message": "Customer ID is required"
      }
    },
    {
      "id": "fact-createorder-http-method",
      "subject_id": "endpoint-createorder-xyz789",
      "predicate": "http_method",
      "object": "POST",
      "evidence": [
        {
          "file": "src/Orders/Controllers/OrderController.cs",
          "line_range": [45, 45]
        }
      ],
      "attributes": {
        "route": "/api/orders"
      }
    },
    {
      "id": "fact-order-business-rule",
      "subject_id": "method-createorder-service-123",
      "predicate": "business_rule",
      "object": "Orders over $1000 require manager approval",
      "evidence": [
        {
          "file": "src/Orders/Services/OrderService.cs",
          "line_range": [78, 85]
        }
      ],
      "attributes": {
        "rule_type": "approval",
        "threshold": 1000
      }
    }
  ]
}
```

### Entity Types Extracted

The fact-graph extracts these entity types:

| Entity Type | Description | Example |
|-------------|-------------|---------|
| `class` | C#/Java classes | `Order`, `Customer` |
| `interface` | Interfaces | `IOrderRepository` |
| `record` | C# records | `OrderDto` |
| `enum` | Enumerations | `OrderStatus` |
| `method` | Class methods | `CreateOrder()` |
| `function` | Standalone functions | `CalculateTax()` |
| `endpoint` | API endpoints | `POST /api/orders` |
| `controller` | MVC controllers | `OrderController` |
| `service` | Service classes | `OrderService` |
| `repository` | Data access | `OrderRepository` |
| `table` | Database tables | `Orders` |
| `view` | Database views | `vw_ActiveOrders` |
| `stored_proc` | Stored procedures | `sp_CreateOrder` |
| `trigger` | Database triggers | `trg_OrderAudit` |
| `sql_function` | SQL functions | `fn_CalculateTotal` |

### Fact Types Extracted

The fact-graph captures these fact types:

| Fact Predicate | Description | Example |
|----------------|-------------|---------|
| `has_property` | Class/entity properties | `Order` has property `TotalAmount` |
| `has_method` | Class methods | `OrderService` has method `CreateOrder` |
| `has_column` | Table columns | `Orders` has column `CustomerId` |
| `validates` | Validation rules | `OrderValidator` validates `Order.TotalAmount > 0` |
| `is_required` | Required fields | `CustomerId` is required |
| `is_nullable` | Nullable fields | `MiddleName` is nullable |
| `is_unique` | Unique constraints | `Email` is unique |
| `max_length` | String length limits | `Name` max length 100 |
| `http_method` | HTTP methods | Endpoint uses `POST` |
| `business_rule` | Business logic | "Orders over $1000 require approval" |
| `integrates_with` | External integrations | Service integrates with `Stripe` |
| `authenticates_via` | Auth methods | API authenticates via `OAuth2` |

### How Skills Use Fact-Graph

All 13 documentation skills (exec-summary-generator through documentation-review) automatically:

1. **Check for fact-graph** at startup (Phase 0)
2. **Load domain-scoped packs** if available
3. **Query entities/relations/facts** using fast O(1) lookups
4. **Fall back to grep/read** if fact-graph unavailable

Example skill execution with fact-graph:

```bash
# Without fact-graph
/legacylift-classic:business-documenter code_path=repos/my_project
# ⏱️ Greps for validation rules...
# ⏱️ Reads 150+ files for each analysis pass...
# ⏱️ O(N) search complexity for entity lookups

# With fact-graph (improved performance)
/legacylift-classic:fact-graph code_path=repos/my_project          # One-time: creates knowledge graph
/legacylift-classic:business-documenter code_path=repos/my_project
# ✅ Loads fact-graph... (fast dictionary load)
# ✅ Queries validation facts... O(1) lookup
# ✅ Eliminates redundant file reads
```

### Best Practices for Fact-Graph

1. **Run fact-graph first** when starting documentation for a new codebase
2. **Re-run fact-graph** when the codebase changes significantly
3. **Keep fact-graph fresh** by regenerating periodically (weekly/monthly)
4. **Version control** the fact-graph with your documentation
5. **Use fact-graph for batch operations** when running multiple skills

### Fact-Graph Performance Benefits

| Metric | Without Fact-Graph | With Fact-Graph | Improvement |
|--------|-------------------|-----------------|-------------|
| Entity lookups | O(N) grep search | O(1) dictionary lookup | Algorithmic improvement |
| File reads | 500+ for large projects | 0 (uses cached data) | Eliminates redundant I/O |
| Consistency | Varies by skill | Deterministic | 100% consistent |
| Multi-skill execution | Repeated analysis | Shared knowledge graph | Significant time savings |

**Note**: Actual performance improvements will vary based on codebase size, complexity, and hardware. The primary benefits are algorithmic (O(1) vs O(N)) and architectural (eliminating redundant analysis).

### Recent Updates

**February 2026**: All 13 documentation skills (skills 2-15) have been updated to automatically integrate with fact-graph:
- ✅ Skills auto-detect fact-graph at startup (Phase 0)
- ✅ Domain-scoped pack files for better organization
- ✅ Seamless fallback to grep/read when fact-graph unavailable
- ✅ No breaking changes - skills work with or without fact-graph

---

## Quick Start

**⚠️ Important**: Before running any skills, configure the model using `/model sonnet[1m]` and append the context management instructions from the section above to your prompts.

### Option A: Full Documentation (Recommended)

```bash
# Step 0: Configure model (REQUIRED)
/model sonnet[1m]

# Step 1: Generate fact-graph (RECOMMENDED for performance)
/legacylift-classic:fact-graph code_path=repos/my_project
# ✅ Creates knowledge graph for fast lookups by all subsequent skills

# Step 2: Generate executive summary (FIRST)
/legacylift-classic:exec-summary-generator code_path=repos/my_project
# ✅ Foundation document for all stakeholders

# Step 3: Generate core documentation (can run in parallel)

# Architecture & Integration (standalone)
/legacylift-classic:si-documenter code_path=repos/my_project
# ✅ Generates: 01-SYSTEM-ARCHITECTURE.md, 04-INTEGRATION-AND-API-GUIDE.md, 05-QUICK-REFERENCE.md

# Data Model Chain (sequential dependencies)
/legacylift-classic:data-documenter code_path=repos/my_project
# ✅ Generates: 02-DATA-MODEL-AND-RELATIONSHIPS.md

# THEN run these in parallel (both depend on data-documenter)
/legacylift-classic:database-layer-documenter domain=YourDomain code_path=repos/my_project
# ✅ Generates: 02-DATA-MODEL-AND-RELATIONSHIPS-{DOMAIN}.md

/legacylift-classic:data-dictionary-generator domain=YourDomain ddl_namespace=YourProject.Database code_path=repos/my_project
# ✅ Generates: 12-DATA-DICTIONARY-{DOMAIN}.md

# Business Requirements Chain (sequential dependencies)
/legacylift-classic:business-documenter code_path=repos/my_project
# ✅ Generates: 03-BUSINESS-RULES-AND-REQUIREMENTS.md

/legacylift-classic:detailed-req-documenter code_path=repos/my_project
# ✅ Generates: 03-BUSINESS-RULES-AND-REQUIREMENTS-{CORE}.md (depends on business-documenter)

/legacylift-classic:use-case-generator domain=YourDomain code_path=repos/my_project
# ✅ Generates: 08-USE-CASES-{DOMAIN}.md (depends on detailed-req-documenter)

/legacylift-classic:user-story-generator domain=YourDomain input_doc=repos/my_project/legacylift-docs/08-USE-CASES-{DOMAIN}.md
# ✅ Generates: 11-USER-STORIES-{DOMAIN}.md (depends on use-case-generator)

# Step 4: Validate ORM mappings
/legacylift-classic:table-validation code_path=repos/my_project
# ✅ Generates: 06-TABLE-VALIDATION-*.md (3 reports)
# ✅ Validates ORM mappings against SQL DDL schema

# Step 5: Validate citations
/legacylift-classic:citation-validator docs_path=repos/my_project/legacylift-docs
# ✅ Generates: 09-CITATION-VALIDATION-REPORT.md
# ✅ Uses fact-graph for fast entity citation validation

# Step 6: Validate accuracy
/legacylift-classic:documentation-review docs_path=repos/my_project/legacylift-docs
# ✅ Generates: 07-DOCUMENTATION-ACCURACY-REPORT.md
# ✅ Uses fact-graph for claim verification

# Step 7: Analyze for gaps
/legacylift-classic:gap-analyzer code_path=repos/my_project
# ✅ Generates: 10-GAP-ANALYSIS-REPORT.md
# ✅ Uses fact-graph for complete code inventory

# Step 8: Fix issues if needed (manual fixes)
# Review the accuracy reports and address identified issues

# Step 9: Re-validate (confirm fixes)
/legacylift-classic:citation-validator docs_path=repos/my_project/legacylift-docs
/legacylift-classic:documentation-review docs_path=repos/my_project/legacylift-docs

# Step 10: Add glossary tables to all docs (polish)
/legacylift-classic:table-of-definitions path=repos/my_project/legacylift-docs/

# Step 11: Export to Word or PDF
/legacylift-classic:doc-exporter path=repos/my_project                      # Individual files
/legacylift-classic:doc-exporter mode=consolidated path=repos/my_project    # Single combined document
/legacylift-classic:doc-exporter format=pdf path=repos/my_project           # PDF output
```

### Option B: Executive Summary Only

```bash
# Configure model first (REQUIRED)
/model sonnet[1m]

# Optional: Generate fact-graph for faster execution
/legacylift-classic:fact-graph code_path=repos/my_project

# Generate executive summary
/legacylift-classic:exec-summary-generator code_path=repos/my_project
# ✅ Uses fact-graph if available for instant LOC metrics and entity counts

# Validate
/legacylift-classic:citation-validator docs_path=repos/my_project/legacylift-docs
/legacylift-classic:documentation-review docs_path=repos/my_project/legacylift-docs
```

### Option C: Specific Documents

```bash
# Configure model first (REQUIRED)
/model sonnet[1m]

# Recommended: Generate fact-graph first for improved performance
/legacylift-classic:fact-graph code_path=repos/my_project

# Generate only what you need
/legacylift-classic:si-documenter code_path=repos/my_project      # Architecture + Integration
/legacylift-classic:data-documenter code_path=repos/my_project    # Data Model
/legacylift-classic:business-documenter code_path=repos/my_project # Business Rules
# ✅ All skills auto-detect and use fact-graph when available

# Then validate
/legacylift-classic:citation-validator docs_path=repos/my_project/legacylift-docs
/legacylift-classic:documentation-review docs_path=repos/my_project/legacylift-docs
```

---

## Skill Details

### Generators

| Skill | Documents Created | Best For |
|-------|-------------------|----------|
| `/legacylift-classic:exec-summary-generator` | 00-EXECUTIVE-SUMMARY.md | Quick overview for stakeholders |
| `/legacylift-classic:si-documenter` | 01-SYSTEM-ARCHITECTURE.md<br>04-INTEGRATION-AND-API-GUIDE.md | Technical architecture focus |
| `/legacylift-classic:data-documenter` | 02-DATA-MODEL-AND-RELATIONSHIPS.md | Conceptual data model and application-level ORM |
| `/legacylift-classic:database-layer-documenter` | 02-DATA-MODEL-AND-RELATIONSHIPS-{DOMAIN}.md | Domain-specific database layer analysis (tables, procedures, triggers, views) |
| `/legacylift-classic:data-dictionary-generator` | 12-DATA-DICTIONARY-{DOMAIN}.md | Exhaustive database-agnostic data dictionary with logical data types for migration planning |
| `/legacylift-classic:business-documenter` | 03-BUSINESS-RULES-AND-REQUIREMENTS.md | Business logic focus |
| `/legacylift-classic:detailed-req-documenter` | 03-BUSINESS-RULES-*.md (multiple) | Deep-dive into requirements |

**Note**: Run multiple skills to build a complete documentation suite (all core documents 00-05).

### Use Case & User Story Generators

| Skill | Output | Best For |
|-------|--------|----------|
| `/legacylift-classic:use-case-generator` | 08-USE-CASES-{DOMAIN}.md | Comprehensive use case documentation per domain with actors, flows, and acceptance criteria |
| `/legacylift-classic:user-story-generator` | 11-USER-STORIES-{DOMAIN}.md | User stories organized into epics with acceptance criteria, generated from use cases |

### Analyzer

| Skill | Output | Purpose |
|-------|--------|---------|
| `/legacylift-classic:gap-analyzer` | 10-GAP-ANALYSIS-REPORT.md | Identifies undocumented code and unimplemented documentation |

### Validators (Feedback Loop)

| Skill | Output | Validates |
|-------|--------|-----------|
| `/legacylift-classic:table-validation` | 06-TABLE-VALIDATION-EXECUTIVE-SUMMARY.md<br>06-TABLE-VALIDATION-COMPREHENSIVE-REPORT.md<br>06-TABLE-VALIDATION-DISCREPANCIES.md | ORM mappings vs SQL DDL schema integrity (Hibernate, NHibernate, Entity Framework) |
| `/legacylift-classic:documentation-review` | 07-DOCUMENTATION-ACCURACY-REPORT.md | Semantic accuracy - technical claims vs actual code |
| `/legacylift-classic:citation-validator` | 09-CITATION-VALIDATION-REPORT.md | Syntactic accuracy - line number citations (e.g., `file.py:123`) |

### Enhancers

| Skill | Output | Purpose |
|-------|--------|---------|
| `/legacylift-classic:table-of-definitions` | Appends section to existing `.md` files | Extracts acronyms and terms, adds a glossary table and updates the Table of Contents |

### Exporters

| Skill | Output | Purpose |
|-------|--------|---------|
| `/legacylift-classic:doc-exporter` | Word (.docx) or PDF (.pdf) | Exports markdown docs via Pandoc with rendered Mermaid diagrams and CapTech branding. Supports individual, consolidated, and single-file modes. Preserves each document's existing Table of Contents |

### Summarizers

| Skill | Output | Purpose |
|-------|--------|---------|
| `/legacylift-classic:repo-summary-generator` | Comprehensive summary document | Analyzes all generated docs and produces metrics, statistics, and facts at a glance for presentations |

---

## Validation Feedback Loop

The validators are designed to be run iteratively until documentation reaches acceptable accuracy:

```
┌─────────────────────────────────────────────────────────┐
│                  VALIDATION LOOP                        │
│                                                         │
│    ┌──────────────┐                                     │
│    │   Generate   │                                     │
│    │    Docs      │                                     │
│    └──────┬───────┘                                     │
│           │                                             │
│           ▼                                             │
│    ┌──────────────┐      ┌──────────────┐               │
│    │  /citation-  │      │/documentation│               │
│    │  validator   │      │   -review    │               │
│    └──────┬───────┘      └──────┬───────┘               │
│           │                     │                       │
│           └──────────┬──────────┘                       │
│                      │                                  │
│                      ▼                                  │
│              ┌───────────────┐                          │
│              │ Accuracy OK?  │                          │
│              │   (≥95%)      │                          │
│              └───────┬───────┘                          │
│                      │                                  │
│           ┌──────────┴──────────┐                       │
│           │                     │                       │
│          NO                    YES                      │
│           │                     │                       │
│           ▼                     ▼                       │
│    ┌──────────────┐      ┌──────────────┐               │
│    │  Manual Fix  │      │    DONE      │               │
│    │   Issues     │      │   ✓ ✓ ✓     │               │
│    └──────┬───────┘      └──────────────┘               │
│           │                                             │
│           └──────────► (re-validate)                    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Target Accuracy Levels

| Level | Score | Recommendation |
|-------|-------|----------------|
| Excellent | ≥95% | Ready for production use |
| Good | 85-94% | Minor fixes recommended |
| Fair | 70-84% | Review and update needed |
| Poor | <70% | Major revision required |

---

## Output Structure

All skills output to a `legacylift-docs/` folder in the target repository:

```
repos/my_project/
├── legacylift-docs/
│   ├── context/                                    # ⭐ Fact-graph knowledge base
│   │   ├── index.json                              # Metadata and statistics
│   │   └── packs/                                  # Domain-scoped data packs
│   │       ├── core.entities.pack.json             # Core domain entities
│   │       ├── core.relations.pack.json            # Core domain relations
│   │       ├── core.facts.pack.json                # Core domain facts
│   │       ├── orders.entities.pack.json           # Orders domain entities
│   │       ├── orders.relations.pack.json          # Orders domain relations
│   │       └── orders.facts.pack.json              # Orders domain facts
│   ├── 00-EXECUTIVE-SUMMARY.md
│   ├── 01-SYSTEM-ARCHITECTURE.md
│   ├── 02-DATA-MODEL-AND-RELATIONSHIPS.md
│   ├── 02-DATA-MODEL-AND-RELATIONSHIPS-{DOMAIN}.md (domain-specific)
│   ├── 03-BUSINESS-RULES-AND-REQUIREMENTS.md
│   ├── 03-BUSINESS-RULES-AND-REQUIREMENTS-{CORE}.md (detailed)
│   ├── 04-INTEGRATION-AND-API-GUIDE.md
│   ├── 05-QUICK-REFERENCE.md
│   ├── 06-TABLE-VALIDATION-EXECUTIVE-SUMMARY.md
│   ├── 06-TABLE-VALIDATION-COMPREHENSIVE-REPORT.md
│   ├── 06-TABLE-VALIDATION-DISCREPANCIES.md
│   ├── 07-DOCUMENTATION-ACCURACY-REPORT.md
│   ├── 08-USE-CASES-{DOMAIN}.md
│   ├── 09-CITATION-VALIDATION-REPORT.md
│   ├── 10-GAP-ANALYSIS-REPORT.md
│   ├── 11-USER-STORIES-{DOMAIN}.md
│   ├── 12-DATA-DICTIONARY-{DOMAIN}.md (database-agnostic data dictionary)
│   ├── docx/                              ← Word exports (/legacylift-classic:doc-exporter)
│   │   ├── 00-EXECUTIVE-SUMMARY.docx
│   │   └── ...
│   └── pdf/                               ← PDF exports (/legacylift-classic:doc-exporter format=pdf)
│       ├── 00-EXECUTIVE-SUMMARY.pdf
│       └── ...
└── (source code files)
```

---

## Common Parameters

Most skills accept these parameters:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `code_path` | Path to source code repository | Current directory |
| `docs_path` | Path to documentation folder | `{code_path}/legacylift-docs/` |
| `output_dir` | Where to write output | `{code_path}/legacylift-docs/` |

---

## Best Practices

1. **Always configure the model first** using `/model sonnet[1m]` and append context management instructions to your prompts (see [Model Configuration](#important-model-configuration-for-large-documentation) section above)

2. **⭐ Generate fact-graph first** using `/legacylift-classic:fact-graph` for improved performance and consistent entity identification across all documentation

3. **Respect skill dependencies** when generating documentation:
   - Start with `/legacylift-classic:exec-summary-generator` (foundation for all)
   - Data chain: `/legacylift-classic:data-documenter` → (`/legacylift-classic:database-layer-documenter` AND `/legacylift-classic:data-dictionary-generator`)
   - Business chain: `/legacylift-classic:business-documenter` → `/legacylift-classic:detailed-req-documenter` → `/legacylift-classic:use-case-generator` → `/legacylift-classic:user-story-generator`
   - `/legacylift-classic:si-documenter` can run in parallel with other chains

4. **Always run validators** after generation:
   - `/legacylift-classic:table-validation` validates ORM mappings against SQL DDL
   - `/legacylift-classic:citation-validator` catches broken line references
   - `/legacylift-classic:documentation-review` catches semantic inaccuracies

5. **Fix identified issues** manually or regenerate problematic sections

6. **Re-validate after fixes** to confirm issues were resolved

7. **Run `/legacylift-classic:gap-analyzer`** periodically to catch documentation drift as code evolves

8. **Target 95%+ accuracy** before considering documentation production-ready

9. **Regenerate fact-graph** when the codebase changes significantly (weekly/monthly for active projects)

10. **Use domain-specific skills** for targeted documentation:
    - `/legacylift-classic:database-layer-documenter` for database layer analysis per domain
    - `/legacylift-classic:use-case-generator` for use case documentation per domain
    - `/legacylift-classic:user-story-generator` for user stories from use cases
    - `/legacylift-classic:data-dictionary-generator` for exhaustive, database-agnostic data dictionaries

11. **Run `/legacylift-classic:table-of-definitions`** as a final polishing step after all documentation is validated. It auto-extracts acronyms and domain terms into a glossary table and adds a link in the document's Table of Contents for easy navigation in Word exports

12. **Use `/legacylift-classic:doc-exporter`** to produce professional Word or PDF deliverables. Mermaid diagrams are automatically rendered as images (requires `mmdc` installed via `npm install -g @mermaid-js/mermaid-cli`). Use `mode=consolidated` for a single combined document

---

## Example: Complete Workflow

```bash
# 0. Configure model first (REQUIRED)
/model sonnet[1m]

# 1. Generate fact-graph (RECOMMENDED for performance)
/legacylift-classic:fact-graph code_path=repos/my_project

# Output:
# ✅ Creates legacylift-docs/context/ directory with:
#    - index.json (metadata and statistics)
#    - packs/*.entities.pack.json (entities by domain)
#    - packs/*.relations.pack.json (relations by domain)
#    - packs/*.facts.pack.json (facts by domain)
# ⏱️ Analysis time: ~60 seconds (one-time investment)

# 2. Generate executive summary (FIRST)
/legacylift-classic:exec-summary-generator code_path=repos/my_project
# Output: 00-EXECUTIVE-SUMMARY.md

# 3. Generate core documentation (respecting dependencies)

# Architecture (standalone)
/legacylift-classic:si-documenter code_path=repos/my_project
# Output: 01-SYSTEM-ARCHITECTURE.md, 04-INTEGRATION-AND-API-GUIDE.md, 05-QUICK-REFERENCE.md

# Data Model Chain
/legacylift-classic:data-documenter code_path=repos/my_project
# Output: 02-DATA-MODEL-AND-RELATIONSHIPS.md

# Then run these in parallel (both depend on data-documenter)
/legacylift-classic:database-layer-documenter domain=Orders code_path=repos/my_project
# Output: 02-DATA-MODEL-AND-RELATIONSHIPS-ORDERS.md

/legacylift-classic:data-dictionary-generator domain=Orders ddl_namespace=MyProject.Database code_path=repos/my_project
# Output: 12-DATA-DICTIONARY-ORDERS.md

# Business Requirements Chain (sequential)
/legacylift-classic:business-documenter code_path=repos/my_project
# Output: 03-BUSINESS-RULES-AND-REQUIREMENTS.md

/legacylift-classic:detailed-req-documenter code_path=repos/my_project
# Output: 03-BUSINESS-RULES-AND-REQUIREMENTS-CORE.md
# ✅ Depends on business-documenter

/legacylift-classic:use-case-generator domain=Orders code_path=repos/my_project
# Output: 08-USE-CASES-ORDERS.md
# ✅ Depends on detailed-req-documenter
# ✅ Uses fact-graph for endpoints, controllers, services

/legacylift-classic:user-story-generator domain=Orders input_doc=repos/my_project/legacylift-docs/08-USE-CASES-ORDERS.md
# Output: 11-USER-STORIES-ORDERS.md
# ✅ Depends on use-case-generator
# ✅ Uses fact-graph for implementation citations

# 4. Validate ORM mappings
/legacylift-classic:table-validation code_path=repos/my_project
# Output: 06-TABLE-VALIDATION-*.md (3 reports)
# ✅ Validates ORM mappings against SQL DDL

# 5. Validate citations
/legacylift-classic:citation-validator docs_path=repos/my_project/legacylift-docs
# Output: 09-CITATION-VALIDATION-REPORT.md
# ✅ Uses fact-graph for entity citation validation

# 6. Validate accuracy
/legacylift-classic:documentation-review docs_path=repos/my_project/legacylift-docs
# Output: 07-DOCUMENTATION-ACCURACY-REPORT.md
# Result: 94.2% accuracy, 2 issues found
# ✅ Uses fact-graph for claim verification

# 7. Analyze for gaps
/legacylift-classic:gap-analyzer code_path=repos/my_project
# Output: 10-GAP-ANALYSIS-REPORT.md
# ✅ Uses fact-graph for O(1) cross-referencing

# 8. Review and manually fix issues if needed
# (Address issues identified in the accuracy report)

# 9. Re-validate to confirm fixes
/legacylift-classic:citation-validator docs_path=repos/my_project/legacylift-docs
/legacylift-classic:documentation-review docs_path=repos/my_project/legacylift-docs
# Result: 97.7% accuracy, 0 issues - DONE!

# 10. Add glossary tables (extracts acronyms/terms, updates Table of Contents)
/legacylift-classic:table-of-definitions path=repos/my_project/legacylift-docs/

# Or process a single file:
/legacylift-classic:table-of-definitions path=repos/my_project/legacylift-docs/ file=00-EXECUTIVE-SUMMARY.md

# 11. Export to Word (individual files per markdown doc)
/legacylift-classic:doc-exporter path=repos/my_project

# Or export a single file
/legacylift-classic:doc-exporter path=repos/my_project file=00-EXECUTIVE-SUMMARY.md

# Or export as a single consolidated Word document
/legacylift-classic:doc-exporter mode=consolidated path=repos/my_project

# Or export to PDF
/legacylift-classic:doc-exporter format=pdf mode=consolidated path=repos/my_project
```

---

## Complete Documentation Ecosystem

LegacyLift generates a comprehensive 12-document ecosystem:

| Prefix | Document | Purpose |
|--------|----------|---------|
| **Core Documentation (00-05)** |||
| 00 | EXECUTIVE-SUMMARY | High-level overview for all stakeholders |
| 01 | SYSTEM-ARCHITECTURE | Technical architecture deep dive |
| 02 | DATA-MODEL-AND-RELATIONSHIPS | Data structures and relationships |
| 03 | BUSINESS-RULES-AND-REQUIREMENTS | Functional requirements and rules |
| 04 | INTEGRATION-AND-API-GUIDE | API documentation and integration patterns |
| 05 | QUICK-REFERENCE | Glossary and quick lookups |
| **Extended Analysis (06-12)** |||
| 06 | TABLE-VALIDATION-* | ORM mapping validation (3 reports) |
| 07 | DOCUMENTATION-ACCURACY-REPORT | Documentation accuracy validation |
| 08 | USE-CASES-{DOMAIN} | Comprehensive use case documentation |
| 09 | CITATION-VALIDATION-REPORT | Citation correctness validation |
| 10 | GAP-ANALYSIS-REPORT | Documentation-code gap analysis |
| 11 | USER-STORIES-{DOMAIN} | User stories organized into epics with acceptance criteria |
| 12 | DATA-DICTIONARY-{DOMAIN} | Exhaustive database-agnostic data dictionary with logical data types |

**Note**: Documents 02, 03, 08, 11, and 12 may have multiple variants (e.g., per domain or per core capability).

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Documentation folder not found" | Ensure `code_path` or `docs_path` is correct |
| Incomplete or truncated documentation | Configure model with `/model sonnet[1m]` and append context management instructions to prompts |
| Documentation generation stops early | Add context management instructions (see Model Configuration section) |
| Slow documentation generation | Run `/legacylift-classic:fact-graph` first for improved performance through O(1) lookups |
| Inconsistent entity names across docs | Regenerate with `/legacylift-classic:fact-graph` for deterministic entity identification |
| Skills not using fact-graph | Check that `legacylift-docs/context/index.json` exists; skills auto-detect it |
| Outdated fact-graph data | Regenerate fact-graph after significant code changes |
| Low accuracy scores | Review issues, make manual fixes, then re-validate |
| Missing citations | Run `/legacylift-classic:citation-validator` to identify broken references |
| Gaps in documentation | Run `/legacylift-classic:gap-analyzer` then update with specific documenters |
| Need use case documentation | Run `/legacylift-classic:use-case-generator` with specific domain parameter |
| Need user stories for implementation | Run `/legacylift-classic:user-story-generator` after generating use cases |
| Need database-agnostic data dictionary | Run `/legacylift-classic:data-dictionary-generator` with domain and DDL namespace parameters for migration planning |
| Mermaid diagrams appear as code in exports | Install mermaid-cli: `npm install -g @mermaid-js/mermaid-cli` |
| Doc export fails with "pandoc not found" | Install Pandoc: `brew install pandoc` (macOS) or `choco install pandoc` (Windows) |
| PDF export fails with `libgobject` error | Install Pango system libraries: `brew install pango` |
| Table of Definitions already exists in doc | Re-run `/legacylift-classic:table-of-definitions` to update; it replaces the existing section |

---

*Generated By LegacyLift AI by CapTech*
