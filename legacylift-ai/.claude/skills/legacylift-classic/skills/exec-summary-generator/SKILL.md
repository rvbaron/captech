---
name: exec-summary-generator
description: Analyzes a codebase and generates an executive summary-level of documentation following industry best practices.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, BashOutput, Task, TodoWrite, Skill, WebFetch
---

# Executive Summary Generator

This skill performs a high-level analysis of a codebase and generates an executive summary suitable for all stakeholders - from executives to engineers.

## Instructions

The exec-summary-generator skill systematically analyzes the codebase using the "Skill Execution" and "Documentation Process" described below, and produces a single file:

1. **00-EXECUTIVE-SUMMARY.md** - High-level overview for all stakeholders (15-20 min read)

## Examples

```
Use the exec-summary-generator skill on this repository.
```

```
Update the project documentation with exec-summary-generator.
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
echo '{"phase": "Load Fact Graph", "phase_number": 0, "total_phases": 7, "progress_percent": 0, "current_task": "Checking for fact graph", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
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
    project_type = index_metadata.get('project_type', 'unknown')
    total_loc = statistics.get('lines_of_code', {}).get('total_loc', 0)
else:
    # Fallback to direct code analysis
    # ... original grep/glob/find commands ...
```

### Phase 1: Initial Discovery (Quick exploration)

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Initial Discovery", "phase_number": 1, "total_phases": 7, "progress_percent": 14, "current_task": "Scanning repository structure", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

- Scan repository structure
- Identify project type (monorepo, web app, microservices, library, etc.)
- Find key configuration files
- Detect technology stack
- Identify entry points
- **Generate Codebase Metrics**: Count lines of code by file type with breakdown

**If fact-graph loaded:**
```python
if fact_graph_loaded:
    # Get LOC metrics from fact-graph
    loc_metrics = statistics.get('lines_of_code', {})
    total_loc = loc_metrics.get('total_loc', 0)
    total_files = loc_metrics.get('total_files', 0)
    by_language = loc_metrics.get('by_language', {})

    # Get project classification
    project_type = index_metadata.get('project_type', 'unknown')
    architecture_pattern = index_metadata.get('architecture_pattern', 'unknown')

    # Get entity counts
    entity_types = statistics.get('entity_types', {})
    num_classes = entity_types.get('class', 0)
    num_interfaces = entity_types.get('interface', 0)
    num_endpoints = entity_types.get('endpoint', 0)

    # Get language breakdown
    languages = statistics.get('languages', {})

    print(f"📊 Repository Metrics:")
    print(f"   Total LOC: {total_loc:,} across {total_files} files")
    print(f"   Project Type: {project_type}")
    print(f"   Architecture: {architecture_pattern}")
    print(f"   Entities: {num_classes} classes, {num_interfaces} interfaces, {num_endpoints} endpoints")
else:
    # Fallback: Direct code analysis
    # Use `find` command to locate all code files (excluding build artifacts, node_modules, legacylift-docs)
    # Count total lines per file type (.java, .js, .py, .cs, .sql, .xml, .jsp, .tsx, etc.)
    # Calculate percentages and create breakdown table
    # Generate observations about codebase composition
    pass
```

### Phase 2: Architecture Analysis

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Architecture Analysis", "phase_number": 2, "total_phases": 7, "progress_percent": 28, "current_task": "Analyzing architectural patterns", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

- Identify architectural patterns (monolith, microservices, layered, etc.)
- Map high-level service/module boundaries
- Analyze dependencies and relationships
- Document deployment configuration
- Map communication patterns

**If fact-graph loaded:**
```python
if fact_graph_loaded:
    # Use pre-classified architecture pattern
    architecture = index_metadata.get('architecture_pattern', 'unknown')
    project_type = index_metadata.get('project_type', 'unknown')

    # Get service/component entities
    services = find_entities_by_type('service')
    controllers = find_entities_by_type('controller')
    endpoints = find_entities_by_type('endpoint')

    # Get dependencies from relations
    service_dependencies = find_relations_by_type('uses')
    service_calls = find_relations_by_type('calls')

    # Get domain classification
    domains = set()
    for entity in entities:
        domain = entity.get('attributes', {}).get('domain')
        if domain:
            domains.add(domain)

    print(f"🏗️ Architecture Analysis:")
    print(f"   Pattern: {architecture}")
    print(f"   Type: {project_type}")
    print(f"   Services: {len(services)}")
    print(f"   Endpoints: {len(endpoints)}")
    print(f"   Domains: {len(domains)}")
    print(f"   Dependencies: {len(service_dependencies)}")

    # Extract frameworks from entity annotations
    frameworks = set()
    for entity in entities:
        annotations = entity.get('attributes', {}).get('annotations', [])
        # Identify framework-specific annotations
        if 'RestController' in str(annotations) or 'Controller' in str(annotations):
            frameworks.add('Spring Boot' if 'RestController' in str(annotations) else 'ASP.NET Core')
        if 'FastEndpoint' in str(annotations):
            frameworks.add('FastEndpoints')
else:
    # Fallback: Manual pattern detection
    # Use grep/glob to analyze architectural patterns
    pass
```

### Phase 3: Data Model Extraction

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Data Model Extraction", "phase_number": 3, "total_phases": 7, "progress_percent": 42, "current_task": "Extracting data entities", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

- Identify data persistence strategies
- Identify data entities
- Extract database schemas
- Map entity relationships
- Document data flows

**If fact-graph loaded:**
```python
if fact_graph_loaded:
    # Get data entities
    models = find_entities_by_type('model')
    tables = find_entities_by_type('table')
    dtos = find_entities_by_type('dto')

    # Get relationships
    fk_relations = find_relations_by_type('foreign_key')

    # Get constraints
    required_facts = find_facts_by_predicate('is_required')
    unique_facts = find_facts_by_predicate('is_unique')

    print(f"💾 Data Model Analysis:")
    print(f"   Models: {len(models)}")
    print(f"   Tables: {len(tables)}")
    print(f"   DTOs: {len(dtos)}")
    print(f"   Relationships: {len(fk_relations)}")
else:
    # Fallback: Manual data model discovery
    pass
```

### Phase 4: Business Logic Analysis

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Business Logic Analysis", "phase_number": 4, "total_phases": 7, "progress_percent": 57, "current_task": "Analyzing business rules", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

- Extract key business rules
- Identify key workflows
- Document high-level functional requirements
- Document validation logic

**If fact-graph loaded:**
```python
if fact_graph_loaded:
    # Get business rules
    business_rules = find_facts_by_predicate('business_rule')

    # Get workflows
    state_transitions = find_facts_by_predicate('state_transition')
    process_steps = find_facts_by_predicate('process_step')

    # Get validation rules
    validations = find_facts_by_predicate('validates')
    required_fields = find_facts_by_predicate('is_required')

    print(f"⚙️ Business Logic Analysis:")
    print(f"   Business Rules: {len(business_rules)}")
    print(f"   State Transitions: {len(state_transitions)}")
    print(f"   Process Steps: {len(process_steps)}")
    print(f"   Validation Rules: {len(validations)}")
else:
    # Fallback: Manual business logic discovery
    pass
```

### Phase 5: API & Integration Mapping (Interface documentation)

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "API & Integration Mapping", "phase_number": 5, "total_phases": 7, "progress_percent": 71, "current_task": "Mapping API endpoints", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

- Document API patterns
- Document authentication methods
- Identify external integrations
- Map event systems

**If fact-graph loaded:**
```python
if fact_graph_loaded:
    # Get API endpoints
    endpoints = find_entities_by_type('endpoint')

    # Get HTTP metadata
    http_methods = find_facts_by_predicate('http_method')
    auth_requirements = find_facts_by_predicate('requires_auth')

    # Get integrations
    integrations = find_facts_by_predicate('integrates_with')
    auth_methods = find_facts_by_predicate('authenticates_via')

    # Build endpoint summary with HTTP methods
    endpoint_summary = {}
    for endpoint in endpoints:
        endpoint_id = endpoint['id']
        route = endpoint.get('attributes', {}).get('route', '')
        method_facts = [f for f in http_methods if f['subject_id'] == endpoint_id]
        method = method_facts[0]['object'] if method_facts else 'UNKNOWN'
        endpoint_summary[endpoint['name']] = f"{method} {route}"

    print(f"🔌 API & Integration Analysis:")
    print(f"   Endpoints: {len(endpoints)}")
    print(f"   Integrations: {len(integrations)}")
    print(f"   Auth Methods: {len(auth_methods)}")
else:
    # Fallback: Manual API discovery
    pass
```

### Phase 6: Document Generation with Inline Citations (Synthesis with Provenance)

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Document Generation", "phase_number": 6, "total_phases": 7, "progress_percent": 85, "current_task": "Generating documentation with citations", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

**CRITICAL: Citations must be generated inline as you write, not added later.**

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

### Phase 7: Review & Polish (Quality assurance)

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Review & Polish", "phase_number": 7, "total_phases": 7, "progress_percent": 95, "current_task": "Reviewing and validating", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

- Verify accuracy against codebase
- Ensure consistency across documents
- Validate all citations point to actual implementations
- Check diagram accuracy
- Add table of contents
- Ensure NO sections lack citations

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

✅ Executive Summary document is generated
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
   - Phase 1: Initial Discovery
   - Phase 2: Architecture Analysis
   - Phase 3: Data Model Extraction
   - Phase 4: Business Logic Analysis
   - Phase 5: API & Integration Mapping
   - Phase 6: Document Generation (with inline citations as you write)
   - Phase 7: Review & Polish

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
   - Placed in `legacylift-docs/` directory within the analyzed repository (use the `output_dir` parameter if provided)
   - Following proven template structures
   - With Mermaid diagrams, exhaustive inline source citations, and cross-links
   - **Every substantive claim backed by verifiable source code references from initial writing**
   - **No section written without citations - they're integral to the writing process**
   - Documents that withstand scrutiny through comprehensive provenance
   - Ready for immediate use by all stakeholders

   When using this skill, you can specify the output directory using the `output_dir` parameter. For example:
   ```
   /legacylift-classic:exec-summary-generator output_dir=repos/my_project/legacylift-docs
   ```
   If no `output_dir` is specified, use `{analyzed_repo_path}/legacylift-docs/` as the default.

5. **Provide Summary**
   - What was documented
   - Key findings and insights
   - Recommendations for improvements

---

## Supporting Files & Templates

This skill uses supporting files in the `templates/` directory to ensure consistent, high-quality documentation output across all projects.

### Template Structure

This skill uses one template:

| Template File | Purpose | Usage |
|---------------|---------|-------|
| **[00-EXECUTIVE-SUMMARY.md](./templates/00-EXECUTIVE-SUMMARY.md)** | Structure for executive overview | Guides high-level system description, stakeholder-focused content |

### LegacyLift Documentation Ecosystem

This skill is part of the comprehensive LegacyLift documentation suite. Here's the complete set of documents available:

| Prefix | Document | Generated By | Description |
|--------|----------|--------------|-------------|
| **Core Documentation Suite** ||||
| 00 | [EXECUTIVE-SUMMARY](./templates/00-EXECUTIVE-SUMMARY.md) ⭐ | **exec-summary-generator** | High-level overview for all stakeholders |
| 01 | SYSTEM-ARCHITECTURE | si-documenter | Technical architecture deep dive |
| 02 | DATA-MODEL-AND-RELATIONSHIPS | data-documenter, database-layer-documenter | Data structures and relationships |
| 03 | BUSINESS-RULES-AND-REQUIREMENTS | business-documenter, detailed-req-documenter | Functional requirements and rules |
| 04 | INTEGRATION-AND-API-GUIDE | si-documenter | API documentation and integration patterns |
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
