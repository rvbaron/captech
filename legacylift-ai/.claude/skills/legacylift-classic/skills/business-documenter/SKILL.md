---
name: business-documenter
description: Analyzes a codebase and generates Business Rules and Requirements following industry best practices.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, BashOutput, Task, TodoWrite, Skill, WebFetch
---

# Project Documenter

This skill performs deep analysis of a codebase and generates comprehensive, professional documentation suitable for business analysts.

## Instructions

The business-documenter skill systematically analyzes your codebase using the "Skill Execution" and "Documentation Process" described below, and produces six interconnected documentation files:

4. **03-BUSINESS-RULES-AND-REQUIREMENTS.md** - Functional requirements and rules (60-70 min read)

## Examples

```
Use the business-documenter skill on this repository.
```

```
Update the project documentation with business-documenter.
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

The skill follows a systematic approach with Phase 0 (fact graph loading) plus 7 documentation phases:

**⚠️ CRITICAL: Citations are NOT a post-processing step. Every claim must be cited AS YOU WRITE IT, during Phase 6. Never write prose first and add citations later - this leads to poor quality citations and extra work.**

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
```

**Usage in Subsequent Phases:**
```python
if fact_graph_loaded:
    # Use fact graph data
    services = find_entities_by_type('service')
    controllers = find_entities_by_type('controller')

    # Get validation rules
    validation_facts = find_facts_by_predicate('validates')
    required_facts = find_facts_by_predicate('is_required')

    # Get business rules
    business_rules = find_facts_by_predicate('business_rule')

    # Get workflows
    state_transitions = find_facts_by_predicate('state_transition')
else:
    # Fallback to direct code analysis
    # ... original grep/glob commands ...
```

### Phase 1: Initial Discovery (Quick exploration)

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Initial Discovery", "phase_number": 1, "total_phases": 4, "progress_percent": 25, "current_task": "Scanning repository structure", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

- Review the Executive Summary file if it exists (legacylift-docs/00-Executive-Summary.md) and other files in the legacylift-docs folder
- Scan repository structure
- Identify project type (monorepo, web app, microservices, library, etc.)
- Find key configuration files
- Detect technology stack
- Identify entry points

### Phase 2: Business Logic Analysis (Domain understanding)

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Business Logic Analysis", "phase_number": 2, "total_phases": 4, "progress_percent": 50, "current_task": "Extracting business rules and workflows", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
```
</status-update>

**Objective**: Extract all business logic, rules, workflows, and functional requirements from the codebase.

#### 2.1 Service Discovery

**If fact-graph loaded:**
```python
if fact_graph_loaded:
    # Get all service and controller entities
    services = find_entities_by_type('service')
    controllers = find_entities_by_type('controller')
    endpoints = find_entities_by_type('endpoint')

    print(f"📊 Found {len(services)} services, {len(controllers)} controllers, {len(endpoints)} endpoints")

    # Group by domain for organized analysis
    for domain in get_domains():
        domain_services = find_entities_by_domain(domain)
        print(f"   {domain}: {len(domain_services)} entities")
else:
    # Fallback: Use Task/Explore to discover services
    # Launch exploration agent to find service classes, controllers
    pass
```

#### 2.2 Validation Logic Extraction

**If fact-graph loaded:**
```python
if fact_graph_loaded:
    # Get all validation facts
    validates_facts = find_facts_by_predicate('validates')
    required_facts = find_facts_by_predicate('is_required')
    max_length_facts = find_facts_by_predicate('max_length')
    range_facts = find_facts_by_predicate('range')

    # Group validations by entity
    validations_by_entity = {}
    for fact in validates_facts + required_facts + max_length_facts + range_facts:
        entity_id = fact['subject_id']
        entity = get_entity_by_id(entity_id)
        if entity:
            entity_name = entity['name']
            if entity_name not in validations_by_entity:
                validations_by_entity[entity_name] = []
            validations_by_entity[entity_name].append({
                'predicate': fact['predicate'],
                'object': fact['object'],
                'evidence': fact['evidence'][0],  # File path and line for citation
                'attributes': fact.get('attributes', {})
            })

    print(f"📊 Found {len(validations_by_entity)} entities with validation rules")
else:
    # Fallback: Grep for FluentValidation patterns, data annotations
    pass
```

#### 2.3 Business Rules Discovery

**If fact-graph loaded:**
```python
if fact_graph_loaded:
    # Get business rule facts
    business_rules = find_facts_by_predicate('business_rule')

    # Organize by domain and entity
    rules_by_domain = {}
    for rule in business_rules:
        entity = get_entity_by_id(rule['subject_id'])
        domain = entity.get('attributes', {}).get('domain', 'Unknown')

        if domain not in rules_by_domain:
            rules_by_domain[domain] = []

        rules_by_domain[domain].append({
            'entity_name': entity['name'],
            'rule_description': rule['object'],
            'evidence': rule['evidence'][0],  # For citation
            'attributes': rule.get('attributes', {})
        })

    print(f"📊 Found {len(business_rules)} business rules across {len(rules_by_domain)} domains")
    for domain, rules in rules_by_domain.items():
        print(f"   {domain}: {len(rules)} rules")
else:
    # Fallback: Manual analysis of service methods for business logic
    pass
```

#### 2.4 Workflow Identification

**If fact-graph loaded:**
```python
if fact_graph_loaded:
    # Get workflow facts
    state_transitions = find_facts_by_predicate('state_transition')
    process_steps = find_facts_by_predicate('process_step')

    # Build workflow diagrams
    workflows = {}
    for transition in state_transitions:
        entity = get_entity_by_id(transition['subject_id'])
        entity_name = entity['name']

        if entity_name not in workflows:
            workflows[entity_name] = {'transitions': [], 'steps': []}

        workflows[entity_name]['transitions'].append({
            'from_state': transition['attributes'].get('from_state'),
            'to_state': transition['attributes'].get('to_state'),
            'condition': transition['attributes'].get('condition'),
            'evidence': transition['evidence'][0]
        })

    # Add process steps
    for step in process_steps:
        entity = get_entity_by_id(step['subject_id'])
        entity_name = entity['name']

        if entity_name not in workflows:
            workflows[entity_name] = {'transitions': [], 'steps': []}

        workflows[entity_name]['steps'].append({
            'step_name': step['object'],
            'step_order': step['attributes'].get('step_order'),
            'evidence': step['evidence'][0]
        })

    print(f"📊 Found {len(workflows)} workflows with {len(state_transitions)} transitions and {len(process_steps)} steps")
else:
    # Fallback: Manual code reading for process flows
    pass
```

#### 2.5 Use Case Derivation

**If fact-graph loaded:**
```python
if fact_graph_loaded:
    # Use endpoints as primary use case indicators
    endpoints = find_entities_by_type('endpoint')

    use_cases = []
    for endpoint in endpoints:
        endpoint_id = endpoint['id']

        # Get HTTP method
        method_facts = [f for f in facts if f['subject_id'] == endpoint_id and f['predicate'] == 'http_method']
        http_method = method_facts[0]['object'] if method_facts else 'UNKNOWN'

        # Get route
        route = endpoint.get('attributes', {}).get('route', '')

        # Get related service calls
        calls_relations = [r for r in relations if r['source_id'] == endpoint_id and r['type'] == 'calls']

        use_cases.append({
            'endpoint_name': endpoint['name'],
            'http_method': http_method,
            'route': route,
            'location': f"{endpoint['file']}:{endpoint['line_range'][0]}",
            'calls': [get_entity_by_id(r['target_id'])['name'] for r in calls_relations]
        })

    print(f"📊 Identified {len(use_cases)} use cases from endpoints")
else:
    # Fallback: Task/Explore to analyze controller methods
    pass
```

**Summary**: In this phase, extract ALL business logic using fact-graph (if available) or direct code analysis. Focus on completeness and accurate citations.

### Domain Ordering Strategy

**Before writing the "Functional Requirements by Domain" section, determine the correct ordering of domains.** Do NOT use arbitrary or alphabetical order. Instead, analyze data dependencies between domains and order them by business process flow.

**Ordering Heuristic** (apply in layers):

1. **Layer 1 — Authentication & Identity**: Entry-point domains (auth, member/user resolution). These always come first since all other domains depend on them.
2. **Layer 2 — Reference Data**: Domains that provide lookup/reference data consumed by other domains (e.g., catalog, product data, user profile). These must precede domains that query them.
3. **Layer 3 — Pricing & Valuation**: Domains that price or value items using reference data (e.g., adjudication, pricing engines). These depend on Layer 2.
4. **Layer 4 — Core Business Logic**: Domains that implement the primary business processes (e.g., suggestion engines, opportunity discovery, claim/order processing). These depend on pricing + reference data.
5. **Layer 5 — Consumer-Facing Output**: Domains that present results to end users (e.g., recommendations, fulfillment). These depend on core logic outputs.
6. **Layer 6 — Supporting/Cross-Cutting**: Domains that provide auxiliary services (e.g., translations, auditing, compliance). These are referenced by but don't block other domains.

**How to apply**:
1. After Phase 2, list all identified domains
2. For each domain, note which other domains' data it consumes and which domains consume its data
3. Assign each domain to a layer based on the heuristic above
4. Within a layer, order by: foundational data producers first, then data consumers
5. Use this ordering when writing Domain 1, Domain 2, Domain 3, etc. in the template

**Example**: If the system has Auth, Users, Catalog, Pricing, Suggestions, Recommendations, and Translations domains:
- Domain 1: Auth (Layer 1)
- Domain 2: Users (Layer 2)
- Domain 3: Catalog (Layer 2)
- Domain 4: Pricing (Layer 3)
- Domain 5: Suggestions (Layer 4)
- Domain 6: Recommendations (Layer 5)
- Domain 7: Translations (Layer 6)

### Phase 3: Document Generation with Inline Citations (Synthesis with Provenance)

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Document Generation", "phase_number": 3, "total_phases": 4, "progress_percent": 75, "current_task": "Generating documentation with citations", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
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

### Phase 4: Review & Polish (Quality assurance)

<status-update required="true">
**⚠️ MANDATORY STATUS UPDATE:** Before starting this phase, you MUST run:
```bash
STATUS_FILE="${SKILL_STATUS_FILE:-/home/node/skill-status/current.json}"
echo '{"phase": "Review & Polish", "phase_number": 4, "total_phases": 4, "progress_percent": 95, "current_task": "Reviewing and validating", "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$STATUS_FILE"
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

**⚠️ MANDATORY: All business requirements documentation must be written incrementally to manage context efficiently and avoid token limits.**

### Why Incremental Writing?
- Long documents (60-70 min read) will exceed context windows if written all at once
- Reading the full file before each append wastes tokens
- Incremental writing allows indefinite document length
- More efficient and reliable for comprehensive documentation

### Initial Setup

1. **Create the initial document** with:
   - Front matter (title, audience, reading time, table of contents)
   - Requirements Overview section
   - First 1-2 functional requirement domains or use case groups
   - Add marker at the end: `<!-- MORE CONTENT TO FOLLOW -->`

Example:
```markdown
# Business Rules & Requirements: {Domain Name}
[front matter...]
## Functional Requirements by Domain
### Domain 1: {First Domain}
[all requirements with citations...]
### Domain 2: {Second Domain}
[all requirements with citations...]
<!-- MORE CONTENT TO FOLLOW -->
```

### For Each Additional Section

2. **Use the Edit tool** to replace the marker with new content:
   - **old_string**: `<!-- MORE CONTENT TO FOLLOW -->`
   - **new_string**: `[NEW DOMAIN OR SECTION]\n\n<!-- MORE CONTENT TO FOLLOW -->`

3. **DO NOT read the full file** before appending - the Edit tool will find and replace the marker

4. **For each section you write:**
   - Search for implementation evidence FIRST using Task/Explore or direct file reads
   - Gather all file paths and line numbers BEFORE writing prose
   - Write the section WITH inline citations as you compose each requirement
   - Never write a functional requirement, business rule, or workflow step without immediately adding its citation
   - Replace the marker and continue to the next section

### Writing Pattern for Each Domain

```
For each domain or major section:
1. Search NOW: Find service methods, validators, controllers, models
2. Gather citations: Collect file:line references for all requirements
3. Write WITH citations:
   - FR-XXX-001: Requirement description [📄](service:line)
   - FR-XXX-002: Requirement description [📄](validator:line)
   - [Continue for all requirements in this domain]
4. Replace marker with: domain content + marker
5. Move to next domain
```

### Recommended Section Breakdown

Write the document in these increments (replace marker after each):
1. **Front Matter + Requirements Overview** (~200-300 lines)
2. **Functional Requirements Domain 1** (~150-200 lines per domain)
3. **Functional Requirements Domain 2** (~150-200 lines per domain)
4. **Functional Requirements Domain 3+** (continue pattern)
5. **Business Rules & Validation** (comprehensive tables with citations)
6. **User Workflows** (sequence diagrams with citations)
7. **Use Cases & User Stories** (representative examples)
8. **Compliance & Security Requirements** (if applicable)
9. **Related Documents + Footer** (final section, remove marker)

### Final Step

5. **Remove the marker** when writing the last section (Related Documents, Footer)
   - **old_string**: `<!-- MORE CONTENT TO FOLLOW -->`
   - **new_string**: `[FINAL SECTION CONTENT]\n\n---\n\n*Generated By LegacyLift AI by CapTech*`

### Key Rules

- ✅ Write domain-by-domain or section-by-section incrementally
- ✅ Replace the marker each time using Edit tool (don't read the whole file)
- ✅ Generate citations DURING writing (not after)
- ✅ Search for evidence BEFORE writing each section
- ✅ Use Edit tool with exact marker text for find/replace
- ❌ DO NOT read the entire file between sections
- ❌ DO NOT write requirements first and add citations later
- ❌ DO NOT skip the marker (always add it until the final section)

### Example Workflow

```
1. Write: Front matter + Requirements Overview + Domain 1-2 + marker
2. Edit: Replace marker with Domain 3-4 + marker
3. Edit: Replace marker with Domain 5-6 + marker
4. Edit: Replace marker with Business Rules section + marker
5. Edit: Replace marker with Workflows section + marker
6. Edit: Replace marker with Use Cases section + marker
7. Edit: Replace marker with Compliance section + marker
8. Edit: Replace marker with Related Docs + footer (no marker)
```

### Token Efficiency

This approach:
- Keeps context usage minimal (only marker location needed, not full file)
- Allows documents of any length to be created
- Maintains citation quality throughout
- Prevents context window exhaustion
- Enables you to write 60-70 min read documents without issues

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

When using this skill, you can specify the output directory using the `output_dir` parameter. For example:
```
/legacylift-classic:business-documenter output_dir=repos/my_project/legacylift-docs
```
If no `output_dir` is specified, use `{analyzed_repo_path}/legacylift-docs/` as the default.
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

✅ All documents are generated
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
   - Placed in `docs/` directory (or specified location)
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

7. **Remove the marker** when writing the last section:
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

### Token Efficiency

This approach:
- Keeps context usage minimal (only marker location needed, not full file)
- Allows documents of any length to be created
- Maintains citation quality throughout
- Prevents context window exhaustion
- Enables you to write 60+ min read documents without issues

---

## Supporting Files & Templates

This skill uses supporting files in the `templates/` directory to ensure consistent, high-quality documentation output across all projects.

### Template Structure

This skill uses one template:

| Template File | Purpose | Usage |
|---------------|---------|-------|
| **[03-BUSINESS-RULES-AND-REQUIREMENTS.md](./templates/03-BUSINESS-RULES-AND-REQUIREMENTS.md)** | Structure for requirements docs | Guides functional requirements, business rules, use cases |

### LegacyLift Documentation Ecosystem

This skill is part of the comprehensive LegacyLift documentation suite. Here's the complete set of documents available:

| Prefix | Document | Generated By | Description |
|--------|----------|--------------|-------------|
| **Core Documentation Suite** ||||
| 00 | EXECUTIVE-SUMMARY | exec-summary-generator | High-level overview for all stakeholders |
| 01 | SYSTEM-ARCHITECTURE | si-documenter | Technical architecture deep dive |
| 02 | DATA-MODEL-AND-RELATIONSHIPS | data-documenter, database-layer-documenter | Data structures and relationships |
| 03 | [BUSINESS-RULES-AND-REQUIREMENTS](./templates/03-BUSINESS-RULES-AND-REQUIREMENTS.md) ⭐ | **business-documenter**, detailed-req-documenter | Functional requirements and rules |
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
