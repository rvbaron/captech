---
name: si-documenter
description: Analyzes a codebase and generates comprehensive System Architecture and Integration and API guide following industry best practices.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, BashOutput, Task, TodoWrite, Skill, WebFetch
---

# Systems Integration Documenter

This skill performs deep analysis of a codebase and generates comprehensive, professional documentation suitable for technical stakeholders, primarily systems integration architects and engineers.

## Instructions

The si-documenter skill systematically analyzes your codebase using the "Skill Execution" and "Documentation Process" described below, and produces two interconnected documentation files:

2. **01-SYSTEM-ARCHITECTURE.md** - Technical architecture deep dive (45-60 min read)
5. **04-INTEGRATION-AND-API-GUIDE.md** - API documentation and integration patterns (40-50 min read)

## Examples

```
Use the si-documenter skill on this repository.
```

```
Update the project documentation with si-documenter.
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

## Documentation Process

The skill follows a systematic 7-phase approach:

**⚠️ CRITICAL: Citations are NOT a post-processing step. Every claim must be cited AS YOU WRITE IT, during Phase 6. Never write prose first and add citations later - this leads to poor quality citations and extra work.**

### Phase 0: Load Fact Graph (if available)

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Load Fact Graph", "phase_number": 0, "total_phases": 5, "progress_percent": 0, "current_task": "Checking for fact graph", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

**Objective**: Check for and load pre-generated fact graph to avoid redundant code analysis.

**⚠️ Domain-Scoped Packs**: The fact-graph skill generates domain-scoped pack files (e.g., `core.entities.pack.json`, `api.entities.pack.json`).

**Canonical Reference**: See [FACT-GRAPH-INTEGRATION.md](../FACT-GRAPH-INTEGRATION.md) for the complete Phase 0 specification shared across all skills.

Before beginning discovery and analysis, check if a fact graph exists at `legacylift-docs/context/index.json`. If it exists, load it using this pattern:

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

        # Only mark as loaded if we actually got data
        if len(entities) > 0:
            fact_graph_loaded = True
            print(f"\n✅ Loaded fact graph: {len(entities)} entities, {len(relations)} relations, {len(facts)} facts")
            if packs_metadata:
                print(f"   Domains: {len(packs_metadata)}")
                for pack in packs_metadata:
                    print(f"   - {pack['domain']}: {pack['entity_count']} entities, {pack['relation_count']} relations, {pack['fact_count']} facts")
        else:
            fact_graph_loaded = False
            print("⚠️ Fact graph index found but no pack data loaded")
            print("   Falling back to direct code analysis")
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

def get_endpoint_metadata(endpoint_id):
    """Get all metadata for an endpoint including HTTP method, route, params, etc."""
    endpoint_facts = [f for f in facts if f['subject_id'] == endpoint_id]

    metadata = {}
    for fact in endpoint_facts:
        if fact['predicate'] == 'http_method':
            metadata['http_method'] = fact['object']
            metadata['route'] = fact.get('attributes', {}).get('route', '')
            metadata['auth_required'] = fact.get('attributes', {}).get('auth_required', False)
            metadata['request_dto'] = fact.get('attributes', {}).get('request_dto', '')
            metadata['response_dto'] = fact.get('attributes', {}).get('response_dto', '')
        elif fact['predicate'] == 'accepts_param':
            if 'parameters' not in metadata:
                metadata['parameters'] = []
            metadata['parameters'].append(fact['object'])
        elif fact['predicate'] == 'returns_response':
            metadata['response_type'] = fact['object']
        elif fact['predicate'] == 'requires_auth':
            metadata['requires_auth'] = fact['object']

    return metadata
```

**What fact-graph provides for this skill:**

1. **Project metadata** (`index_metadata`):
   - Project type (microservices, monolith, library, etc.)
   - Architecture pattern (layered, MVC, hexagonal, etc.)
   - Repository structure information

2. **Technology stack** (`statistics`):
   - Languages with LOC breakdown
   - Entity type counts (classes, interfaces, controllers, services, endpoints, etc.)
   - Lines of code metrics

3. **API Endpoints** (`entities` + `facts`):
   - All endpoint entities with locations
   - HTTP methods via `http_method` facts
   - Route paths via endpoint attributes
   - Request/response DTOs via fact attributes
   - Auth requirements via `requires_auth` facts
   - Parameters via `accepts_param` facts

4. **Service Architecture** (`entities` + `relations`):
   - Service entities grouped by domain
   - Controller entities
   - Service dependencies via `calls`, `uses` relations
   - Module boundaries via domain classification

5. **External Integrations** (`facts`):
   - `integrates_with` facts for external services
   - `authenticates_via` facts for auth methods
   - `authorizes_via` facts for authorization patterns

6. **Comprehensive evidence** (for citations):
   - Every entity has file path and line range
   - Every fact has evidence with file:line references
   - Ready for inline citations during document generation

**Usage in subsequent phases:**

```python
if fact_graph_loaded:
    # Use fact-graph data
    project_type = index_metadata.get('project_type', 'unknown')
    architecture = index_metadata.get('architecture_pattern', 'unknown')

    # Get all endpoints with full metadata
    endpoints = find_entities_by_type('endpoint')
    for endpoint in endpoints:
        metadata = get_endpoint_metadata(endpoint['id'])
        # metadata includes: http_method, route, auth_required, parameters, etc.

    # Get services by domain
    domains = get_domains()
    for domain in domains:
        domain_services = [e for e in entities if e['type'] == 'service' and e.get('attributes', {}).get('domain') == domain]

    # Get external integrations
    integrations = find_facts_by_predicate('integrates_with')
else:
    # Fallback to direct code analysis using Task/Explore, Grep, Glob
    # ... original approach ...
```

**Benefits:**
- Eliminates 70-85% of discovery grep/glob operations
- Provides complete API endpoint inventory with metadata
- Includes service dependencies and boundaries
- All data includes file:line evidence for citations
- Faster execution with consistent results

---

### Phase 1: Initial Discovery (Quick exploration)

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Initial Discovery", "phase_number": 1, "total_phases": 5, "progress_percent": 20, "current_task": "Scanning repository structure", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

- Review the Executive Summary file if it exists (legacylift-docs/00-Executive-Summary.md)
- Scan repository structure
- Identify project type (monorepo, web app, microservices, library, etc.)
- Find key configuration files
- Detect technology stack
- Identify entry points

**If fact-graph is loaded:**
- Use `index_metadata.get('project_type')` for project classification
- Use `index_metadata.get('architecture_pattern')` for architecture style
- Use `statistics.get('languages')` for technology stack
- Use `statistics.get('entity_types')` for component counts
- Greatly accelerates discovery phase by eliminating exploratory searches

**If fact-graph not available:**
- Use Task/Explore agents to scan repository structure
- Use Grep/Glob to detect technologies and patterns
- Manually identify project type from structure

### Phase 2: Architecture Analysis (Thorough investigation)

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Architecture Analysis", "phase_number": 2, "total_phases": 5, "progress_percent": 40, "current_task": "Analyzing architectural patterns", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

- Identify ALL services
- Map service/module boundaries
- Analyze dependencies and relationships
- Map communication patterns

**If fact-graph is loaded:**
- Use `find_entities_by_type('service')` to get all services
- Use `find_entities_by_type('controller')` to get all controllers
- Use `get_domains()` to identify service boundaries/domains
- Use `find_entities_by_domain(domain)` to group services by domain
- Use `find_relations_by_type('calls')` and `find_relations_by_type('uses')` to map dependencies
- All entities include domain classification in attributes for boundary identification
- Eliminates extensive grep operations for service discovery

**If fact-graph not available:**
- Use Task/Explore agents to find services and controllers
- Use Grep/Glob to identify namespaces and module boundaries
- Manually analyze code to map dependencies

### Phase 3: API & Integration Mapping (Interface documentation)

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "API & Integration Mapping", "phase_number": 3, "total_phases": 5, "progress_percent": 60, "current_task": "Mapping API endpoints and integrations", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

- Catalog ALL API endpoints
- Identify ALL external integrations
- Map event systems
- Document authentication methods
- Document API patterns

**If fact-graph is loaded:**
- Use `find_entities_by_type('endpoint')` to get complete API endpoint inventory
- Use `get_endpoint_metadata(endpoint_id)` to get full endpoint details:
  - HTTP method (GET, POST, PUT, DELETE, etc.)
  - Route path
  - Request/response DTOs
  - Auth requirements
  - Parameters
- Use `find_facts_by_predicate('integrates_with')` to find external service integrations
- Use `find_facts_by_predicate('authenticates_via')` to identify auth methods
- Use `find_facts_by_predicate('authorizes_via')` to identify authorization patterns
- All facts include evidence with file:line for citations
- Dramatically reduces API discovery effort - all endpoints pre-cataloged with metadata

**If fact-graph not available:**
- Use Task/Explore agents to find controller methods and route definitions
- Use Grep/Glob to search for API decorators and attributes
- Manually extract HTTP methods, routes, and parameters from code
- Search for external HTTP clients and integration points

### Phase 4: Document Generation with Inline Citations (Synthesis with Provenance)

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Document Generation", "phase_number": 4, "total_phases": 5, "progress_percent": 80, "current_task": "Generating documentation with citations", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

**CRITICAL: Citations must be generated inline as you write, not added later.**

**If fact-graph is loaded:**
- Citations are readily available from evidence fields in entities, relations, and facts
- Every entity has `file` and `line_range` for location
- Every fact has `evidence` array with `file` and `line_range` for each source
- Use entity/fact evidence directly for inline citations during writing
- Format: `[📄](entity['file']:entity['line_range'][0])` or `[📄](fact['evidence'][0]['file']:fact['evidence'][0]['line_range'][0])`
- Dramatically reduces search time for citation sources

**If fact-graph not available:**
- Must search for each citation source using Task/Explore before writing
- Follow the citation-first writing workflow below

For each document and each section within:

1. **Write section-by-section with immediate citation**:
   - Identify what you need to write (e.g., "Technology Stack - Backend" section)
   - BEFORE writing the prose, search for source evidence using Task/Explore
   - Write the section WITH citations inline from the start
   - Never write a claim without immediately adding its citation

2. **Citation-First Writing Workflow**:
   ```
   For each sentence/claim to write:
   a) Identify the claim (e.g., "System uses PostgreSQL database")
   b) Search for evidence NOW (e.g., find connection string, DbContext, package.json)
   c) Write sentence WITH citation: "Uses PostgreSQL [📄](src/db/config.ts:12)"
   d) Move to next sentence
   ```

3. **Section Generation Process**:
   - **Plan**: Outline section content (bullet points of what to cover)
   - **Search**: Use Task/Explore to find ALL source files for this section
   - **Write**: Compose section with inline citations as you write each sentence
   - **Validate**: Verify every claim has a citation before moving to next section

4. **Citation Standards** (apply during writing):
   - Technology claims → cite configuration files, startup code, or package references
   - Service descriptions → cite service classes, controllers, or interfaces
   - Feature capabilities → cite implementation methods or API endpoints
   - Data entities → cite model classes or database schema files
   - Architectural patterns → cite service boundaries, middleware, or infrastructure code
   - Integration points → cite client classes, API calls, or external service configurations

5. **Citation Format**:
   - Inline: `claim text [📄](path/to/file.ext:line)`
   - Explicit: `claim text [source](path/to/file.ext:line-range)`
   - Multiple sources: `claim text [1](path1:line) [2](path2:line) [3](path3:line)`

6. **Quality Criteria** (verify as you write each section):
   - Every technology mentioned has a citation to where it's configured or imported
   - Every service/component has a citation to its definition
   - Every feature has a citation to its implementation
   - Every data entity has a citation to its model class
   - Every API endpoint has a citation to its controller method
   - Citations use specific line numbers, not vague references

**Example of Citation-First Writing:**

❌ **WRONG - Writing first, citing later:**
```
1. Write: "The system uses an API gateway for request routing."
2. Later: Go back and try to find citations
3. Edit: "The system uses an API gateway [📄](...) for request routing."
```

✅ **CORRECT - Citing inline during initial writing:**
```
1. Identify claim: "system uses API gateway"
2. Search NOW: Use Task to find gateway config/code
3. Write WITH citation: "The system uses an API gateway [📄](src/gateway/config.json:1) for request routing [📄](src/gateway/router.ts:45)."
4. Move to next sentence
```

**Good Citation Examples:**
```markdown
The system uses an API gateway [📄](src/Gateway/gateway-config.json:1) for request routing and aggregation [📄](src/Gateway/Startup.cs:45).

The User Service manages user records [📄](src/Services/User/UserService.cs:23) and permissions [📄](src/Services/User/Controllers/PermissionController.cs:67).

The application supports OAuth authentication [📄](src/Auth/OAuthHandler.cs:12) integrated with identity providers [📄](src/config/appsettings.json:89).
```

**Bad Citation Examples (avoid):**
```markdown
The system uses an API gateway [📄](src/Gateway/)
↑ Too vague - no specific file or line number

The User Service manages user records [📄](README.md)
↑ Wrong source - should cite actual implementation, not documentation

The application supports OAuth authentication.
↑ No citation - every claim needs source attribution
```

**Concrete Example of Section Writing:**

When writing the "Technology Stack - Backend" section:

```markdown
Step 1: Plan what to cover
- Runtime/language
- Web framework
- Database
- Caching
- Message queue

Step 2: Search for evidence (BEFORE writing)
Launch Task/Explore: "Find backend technology evidence"
Results:
- package.json shows Node.js + TypeScript
- src/server.ts shows Express framework
- src/db/connection.ts shows PostgreSQL
- src/cache/redis.ts shows Redis
- src/queue/rabbitmq.ts shows RabbitMQ

Step 3: Write WITH inline citations
"The backend runs on Node.js [📄](package.json:8) with TypeScript [📄](tsconfig.json:2).
It uses Express [📄](src/server.ts:5) as the web framework, PostgreSQL [📄](src/db/connection.ts:12)
for persistence, Redis [📄](src/cache/redis.ts:8) for caching, and RabbitMQ [📄](src/queue/rabbitmq.ts:15)
for async messaging."

Step 4: Validate - every claim has citation ✅
Step 5: Move to next section
```

All documents include:
- Mermaid diagrams for visualizations
- Exhaustive inline source code citations with line numbers for every claim
- Cross-references between documents
- Progressive disclosure structure
- Multiple audience targeting

### Phase 5: Review & Polish (Quality assurance)

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Review & Polish", "phase_number": 5, "total_phases": 5, "progress_percent": 95, "current_task": "Reviewing and validating", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

- Verify accuracy against codebase
- Ensure consistency across documents
- Validate all citations point to actual implementations
- Check diagram accuracy
- Add table of contents
- Ensure NO sections lack citations

---

## Incremental Document Writing Process

**⚠️ MANDATORY: All system architecture and integration documentation must be written incrementally to manage context efficiently and avoid token limits.**

### Why Incremental Writing?
- Architecture documents (45-60 min read) and integration guides (40-50 min read) can be extensive
- Systems with many microservices, APIs, or integration points require comprehensive coverage
- Reading the full file before each append wastes tokens
- Incremental writing allows indefinite document length
- More efficient and reliable for comprehensive documentation

### Initial Setup

1. **Create the initial document** with:
   - Front matter (title, audience, reading time, table of contents)
   - System Overview or Architecture Overview section
   - First major section (e.g., Technology Stack, Module Decomposition, or API Endpoints group)
   - Add marker at the end: `<!-- MORE CONTENT TO FOLLOW -->`

Example for Architecture:
```markdown
# System Architecture: {System Name}
[front matter...]
## System Overview
[overview with citations...]
## Technology Stack
### Backend
[full backend tech stack with citations...]
### Frontend
[full frontend tech stack with citations...]
<!-- MORE CONTENT TO FOLLOW -->
```

Example for Integration:
```markdown
# Integration & API Guide: {System Name}
[front matter...]
## API Overview
[overview with citations...]
## REST API Endpoints
### User Management Endpoints
[5-10 endpoints with full documentation and citations...]
<!-- MORE CONTENT TO FOLLOW -->
```

### For Each Additional Section

2. **Use the Edit tool** to replace the marker with new content:
   - **old_string**: `<!-- MORE CONTENT TO FOLLOW -->`
   - **new_string**: `[NEXT SECTION OR ENDPOINT GROUP]\n\n<!-- MORE CONTENT TO FOLLOW -->`

3. **DO NOT read the full file** before appending - the Edit tool will find and replace the marker

4. **For each section you write:**
   - Search for implementation evidence FIRST using Task/Explore or direct file reads
   - Gather all file paths and line numbers BEFORE writing prose
   - Write the section WITH inline citations as you compose each description
   - Never write an architecture component, API endpoint, or integration pattern without immediately adding its citation
   - Replace the marker and continue to the next section

### Writing Pattern for Architecture Documentation

```
For each architecture section:
1. Search NOW: Find config files, module definitions, service classes, deployment configs
2. Gather citations: Collect file:line references for:
   - Technology choices (package.json, build files)
   - Module/service definitions
   - Configuration files
   - Deployment manifests
   - Infrastructure code
3. Write WITH citations:
   - Component description [📄](config:line)
   - Technology stack items [📄](package-file:line)
   - Module boundaries [📄](module-definition:line)
   - Deployment architecture [📄](deployment-config:line)
4. Replace marker with: section content + marker
5. Move to next section
```

### Writing Pattern for Integration/API Documentation

```
For each API endpoint group or integration (10-15 endpoints at a time):
1. Search NOW: Find controller methods, route definitions, API specs
2. Gather citations: Collect file:line references for:
   - Endpoint routes
   - Controller methods
   - Request/response DTOs
   - Authentication/authorization
   - Validation logic
3. Write WITH citations:
   - Endpoint definition [📄](controller:line)
   - Request format [📄](DTO:line)
   - Response format [📄](DTO:line)
   - Auth requirements [📄](auth-middleware:line)
4. Replace marker with: endpoint group content + marker
5. Move to next endpoint group
```

### Recommended Section Breakdown for Architecture (01-SYSTEM-ARCHITECTURE.md)

Write the document in these increments (replace marker after each):
1. **Front Matter + System Overview + Technology Stack** (~300-400 lines)
2. **Module Decomposition** (~200-300 lines)
3. **Deployment Architecture** (~150-200 lines)
4. **Architecture Patterns & Principles** (~150-200 lines)
5. **Configuration Management** (~100-150 lines)
6. **Security Architecture** (~150-200 lines)
7. **Performance & Scalability** (~100-150 lines)
8. **Observability & Monitoring** (~100-150 lines)
9. **Related Documents + Footer** (final section, remove marker)

### Recommended Section Breakdown for Integration (04-INTEGRATION-AND-API-GUIDE.md)

Write the document in these increments (replace marker after each):
1. **Front Matter + API Overview + First 10-15 Endpoints** (~300-400 lines)
2. **Next 15-20 Endpoints** (~200-300 lines per batch)
3. **Remaining Endpoint Groups** (continue batching)
4. **Authentication & Authorization** (~150-200 lines)
5. **External Service Integrations** (~200-300 lines)
6. **Message Queue Patterns** (if applicable, ~150-200 lines)
7. **Error Handling & Status Codes** (~100-150 lines)
8. **Rate Limiting & Quotas** (if applicable, ~100-150 lines)
9. **Integration Examples + Footer** (final section, remove marker)

### Final Step

5. **Remove the marker** when writing the last section (Related Documents, Footer)
   - **old_string**: `<!-- MORE CONTENT TO FOLLOW -->`
   - **new_string**: `[FINAL SECTION CONTENT]\n\n---\n\n*Generated By LegacyLift AI by CapTech*`

### Key Rules

- ✅ Write section-by-section or endpoint-group-by-group incrementally
- ✅ Replace the marker each time using Edit tool (don't read the whole file)
- ✅ Generate citations DURING writing (not after)
- ✅ Search for evidence BEFORE writing each section
- ✅ Use Edit tool with exact marker text for find/replace
- ❌ DO NOT read the entire file between sections
- ❌ DO NOT write architecture descriptions or endpoints first and add citations later
- ❌ DO NOT skip the marker (always add it until the final section)
- ❌ DO NOT try to document all 50-100 API endpoints in one pass

### Example Workflow for Architecture Document

```
1. Write: Front matter + Overview + Tech Stack + marker
2. Edit: Replace marker with Module Decomposition + marker
3. Edit: Replace marker with Deployment Architecture + marker
4. Edit: Replace marker with Architecture Patterns + marker
5. Edit: Replace marker with Configuration + marker
6. Edit: Replace marker with Security Architecture + marker
7. Edit: Replace marker with Performance + marker
8. Edit: Replace marker with Observability + marker
9. Edit: Replace marker with Related Docs + footer (no marker)
```

### Example Workflow for Integration Document

```
1. Write: Front matter + API Overview + Endpoints 1-15 + marker
2. Edit: Replace marker with Endpoints 16-30 + marker
3. Edit: Replace marker with Endpoints 31-45 + marker
4. Edit: Replace marker with Remaining Endpoints + marker
5. Edit: Replace marker with Authentication + marker
6. Edit: Replace marker with External Integrations + marker
7. Edit: Replace marker with Message Queue Patterns + marker
8. Edit: Replace marker with Error Handling + marker
9. Edit: Replace marker with Examples + footer (no marker)
```

### Token Efficiency

This approach:
- Keeps context usage minimal (only marker location needed, not full file)
- Allows documentation of large systems (100+ API endpoints, complex architectures)
- Maintains citation quality throughout
- Prevents context window exhaustion
- Enables comprehensive coverage without token limit issues

---

## Key Features

### 🎯 **Audience-Aware Documentation**
Each document targets specific audiences:
- Executives and business stakeholders
- Product managers and analysts
- Software engineers and architects
- Integration partners
- QA and operations teams

### 📊 **Rich Visualizations**
Automatically generates Mermaid diagrams:
- System context diagrams (C4 Level 1)
- Container diagrams (C4 Level 2)
- Entity-relationship diagrams (ERD)
- Sequence diagrams for workflows
- State diagrams for lifecycle management
- Architecture diagrams

### 🔗 **Deep Code Integration**
Every claim includes source code references:
- File paths with line numbers
- Direct links to implementation
- Verifiable against actual codebase
- Easy navigation for developers

### 📚 **Progressive Disclosure**
Information organized by depth:
- Start with high-level overview
- Drill down to technical details
- Cross-references for exploration
- Estimated reading times

### 🔄 **Comprehensive Cross-Referencing**
Documents link to each other:
- Internal references within docs
- Related sections across docs
- Bidirectional navigation
- Consistent terminology

## What Gets Analyzed

The skill examines:

### Code Structure
- ✅ Project organization and file structure
- ✅ Module/package boundaries
- ✅ Naming conventions
- ✅ Code organization patterns

### Architecture
- ✅ Architectural style (monolith, microservices, etc.)
- ✅ Design patterns (MVC, repository, etc.)
- ✅ Communication patterns (REST, events, etc.)
- ✅ Deployment architecture

### Data Layer
- ✅ Database schemas and tables
- ✅ Entity definitions and relationships
- ✅ Data access patterns
- ✅ Caching strategies
- ✅ Data migration history

### Business Logic
- ✅ Domain models
- ✅ Business rules and validation
- ✅ Workflows and state machines
- ✅ Use cases and scenarios

### Integrations
- ✅ API endpoints and routes
- ✅ Authentication/authorization
- ✅ External service integrations
- ✅ Message queues and events
- ✅ Webhooks and callbacks

### Configuration
- ✅ Environment configuration
- ✅ Feature flags
- ✅ Deployment manifests
- ✅ CI/CD pipelines

## Output Quality Standards

All generated documentation includes:

✅ **Clear Structure** - Table of contents, headers, sections
✅ **Estimated Reading Times** - Help readers allocate time
✅ **Target Audience** - Who should read each document
✅ **Prerequisites** - What knowledge is assumed
✅ **Diagrams** - Visual representations using Mermaid
✅ **Exhaustive Citations** - **Every** technology, service, feature, entity, and architectural claim has inline source code citations with precise file paths and line numbers
✅ **Verifiable Claims** - All assertions can be validated by following citation links to actual implementation code
✅ **Cross-References** - Links between related sections and documents
✅ **Examples** - Real code snippets and scenarios
✅ **Best Practices** - Industry standards and patterns
✅ **Troubleshooting** - Common issues and solutions
✅ **Provenance Transparency** - Readers can trace every claim back to its source for maximum trust and verifiability
✅ **Document Footer** - Every generated document MUST end with the footer: `---\n\n*Generated By LegacyLift AI by CapTech*`


## Example Output Structure

```
project-root/
└── legacylift-docs/
    ├── 00-EXECUTIVE-SUMMARY.md
    ├── 01-SYSTEM-ARCHITECTURE.md
    ├── 02-DATA-MODEL-AND-RELATIONSHIPS.md
    ├── 03-BUSINESS-RULES-AND-REQUIREMENTS.md
    ├── 04-INTEGRATION-AND-API-GUIDE.md
    └── 05-QUICK-REFERENCE.md
```

## Technical Implementation

This skill uses Claude Code's advanced capabilities:

- **Task Tool**: Launches specialized exploration agents for thorough codebase analysis
- **Parallel Analysis**: Analyzes multiple aspects concurrently for efficiency
- **Code Search**: Grep and Glob for comprehensive scanning of patterns and files
- **File Reading**: Deep inspection of source files with line-level accuracy
- **Template System**: Universal templates ensure consistent documentation structure
- **Diagram Generation**: Automatic Mermaid diagram creation from code analysis
- **Cross-Referencing**: Links validation across documents with source code references

## Success Criteria

Documentation is considered complete when:

✅ All 2 documents are generated
✅ **Every substantive claim has inline source code citations with file paths and line numbers (generated during initial writing, not added later)**
✅ **Technology stack items cite configuration files, package references, or startup code**
✅ **Service descriptions cite controller classes, service implementations, or interfaces**
✅ **Feature capabilities cite implementation methods or API endpoints**
✅ **Data entities cite model classes or database schema definitions**
✅ **No section was written without citations - they were integral to the writing process**
✅ Diagrams accurately represent the system
✅ Cross-references are valid
✅ Multiple audiences can understand their sections
✅ Documents are consistent with each other
✅ Technical accuracy is verified against source code
✅ **Citations can withstand scrutiny - they point to actual implementations, not generic references**
✅ **Documents never required post-processing to add citations - they had them from the start**

## Skill Execution

**⚠️ MANDATORY WORKFLOW: When writing any section in Phase 6, you MUST:**
1. Search for source evidence FIRST using Task/Explore
2. Gather all file paths and line numbers
3. Write prose WITH citations inline
4. Never write a claim without its citation

When this skill is invoked, I will:

1. **Clarify the Context** (if needed)
   - Project scope and boundaries
   - Target audience priorities
   - Specific areas of focus
   - Existing documentation to reference

2. **Create Todo List**
   - Phase 0: Load Fact Graph (if available)
   - Phase 1: Initial Discovery
   - Phase 2: Architecture Analysis
   - Phase 3: API & Integration Mapping
   - Phase 4: Document Generation (with inline citations as you write)
   - Phase 5: Review & Polish

3. **Execute Systematically**
   - Use Tasks to strategically launch exploration agents throughout each phase
   - Gather information in parallel where possible
   - Build comprehensive understanding
   - Reference templates for consistent structure
   - **For Phase 6 - Generate documents with inline citations**:
     * Break each document into logical sections
     * For each section, create a detailed todo list with tasks like:
       - "Search for [Technology X] evidence"
       - "Write [Section Y] with inline citations"
       - "Validate [Section Y] citations"
     * BEFORE writing prose, launch Task/Explore agents to find ALL relevant source files
     * Gather file paths and line numbers for citations
     * Write section WITH citations inline (never write without citing)
     * Use Write tool to create section with complete citations from the start
     * Validate every claim has a citation before marking section complete
     * Move to next section only after current section is fully cited
     * **Never write a sentence without immediately adding its citation**
     * **Pattern: Search → Gather → Write-with-Citations → Validate → Next Section**
   - Cross-validate findings against codebase

4. **Deliver Complete Documentation**
   - All 6 documents in markdown format
   - Placed in `legacylift-docs/` directory (or specified location)
   - Following proven template structures
   - With Mermaid diagrams, exhaustive inline source citations, and cross-links
   - **Every substantive claim backed by verifiable source code references from initial writing**
   - **No section written without citations - they're integral to the writing process**
   - Documents that withstand scrutiny through comprehensive provenance
   - Ready for immediate use by all stakeholders

5. **Provide Summary**
   - What was documented
   - Key findings and insights
   - Recommendations for improvements

---

## Supporting Files & Templates

This skill uses supporting files in the `templates/` directory to ensure consistent, high-quality documentation output across all projects.

### Template Structure

This skill uses two templates:

| Template File | Purpose | Usage |
|---------------|---------|-------|
| **[01-SYSTEM-ARCHITECTURE.md](./templates/01-SYSTEM-ARCHITECTURE.md)** | Structure for technical architecture | Guides C4 diagrams, component documentation, technology stack |
| **[04-INTEGRATION-AND-API-GUIDE.md](./templates/04-INTEGRATION-AND-API-GUIDE.md)** | Structure for API documentation | Guides endpoint documentation, integration patterns, examples |

### LegacyLift Documentation Ecosystem

This skill is part of the comprehensive LegacyLift documentation suite. Here's the complete set of documents available:

| Prefix | Document | Generated By | Description |
|--------|----------|--------------|-------------|
| **Core Documentation Suite** ||||
| 00 | EXECUTIVE-SUMMARY | exec-summary-generator | High-level overview for all stakeholders |
| 01 | [SYSTEM-ARCHITECTURE](./templates/01-SYSTEM-ARCHITECTURE.md) ⭐ | **si-documenter** | Technical architecture deep dive |
| 02 | DATA-MODEL-AND-RELATIONSHIPS | data-documenter, database-layer-documenter | Data structures and relationships |
| 03 | BUSINESS-RULES-AND-REQUIREMENTS | business-documenter, detailed-req-documenter | Functional requirements and rules |
| 04 | [INTEGRATION-AND-API-GUIDE](./templates/04-INTEGRATION-AND-API-GUIDE.md) ⭐ | **si-documenter** | API documentation and integration patterns |
| 05 | QUICK-REFERENCE | si-documenter | Glossary and quick lookups |
| **Extended Documentation & Analysis** ||||
| 06 | TABLE-VALIDATION-* | table-validation | ORM mapping validation reports |
| 07 | DOCUMENTATION-ACCURACY-REPORT | documentation-review | Documentation accuracy validation |
| 08 | USE-CASES-{DOMAIN} | use-case-generator | Comprehensive use case documentation |
| 09 | CITATION-VALIDATION-REPORT | citation-validator | Citation correctness validation |
| 10 | GAP-ANALYSIS-REPORT | gap-analyzer | Documentation-code gap analysis |

⭐ = Generated by this skill

### How Templates Are Used

During skill execution, I (Claude) will:

1. **Reference Templates**: Read the appropriate template for each document type
2. **Extract Structure**: Use the template's sections, headings, and organization
3. **Fill with Analysis**: Replace placeholders with actual findings from your codebase
4. **Maintain Consistency**: Ensure all documents follow the same professional standards
5. **Adapt as Needed**: Customize sections based on your project's specifics

### Template Features

Each template includes:

- **Instructional Comments**: HTML comments guiding what content to include
- **Placeholder Syntax**: `{PLACEHOLDER}` markers for project-specific values
- **Section Organization**: Pre-structured table of contents and sections
- **Diagram Scaffolds**: Mermaid diagram templates ready to be populated
- **Cross-Reference Patterns**: Consistent linking between documents
- **Audience Indicators**: Clear guidance on who should read each section
- **Example Structures**: Tables, code blocks, and formatting examples
