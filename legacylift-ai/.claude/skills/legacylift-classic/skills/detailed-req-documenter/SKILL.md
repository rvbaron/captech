---
name: detailed-req-documenter
description: Analyzes a codebase and generates DOMAIN-specific Business Rules and Requirements following industry best practices.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, BashOutput, Task, TodoWrite, Skill, WebFetch
---

# Project Documenter

This skill performs deep analysis of a codebase and generates comprehensive, professional documentation suitable for business analysts.

## Instructions

The business-documenter skill systematically analyzes your codebase using the "Skill Execution" and "Documentation Process" described below, and produces the following documentation files for each Core Capability in the Executive Summary (or the Core Capability specified in the prompt):

4. **03-BUSINESS-RULES-AND-REQUIREMENTS-CORE_CAPABILITY_NAME.md** - Functional requirements and rules (60-70 min read)

## Examples

```
Use the detailed-req-documenter skill on this repository.
```

```
Update the project documentation with detailed-req-documenter.
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

The skill follows a systematic 4-phase approach for **each** Core Capability:

**⚠️ CRITICAL: Citations are NOT a post-processing step. Every claim must be cited AS YOU WRITE IT. Never write prose first and add citations later - this leads to poor quality citations and extra work.**

### Perform Phases 0-4 for **each** Core Capability in the 00-EXECUTIVE-SUMMARY.md file in this repo.

### Phase 0: Load Fact Graph (if available)

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

def find_entities_by_capability(capability):
    """Find all entities in a given capability"""
    return [e for e in entities if e.get('attributes', {}).get('capability') == capability]

def find_entity_by_name(name):
    """Find entity by exact name match"""
    return next((e for e in entities if e['name'] == name), None)

def find_facts_by_predicate(predicate):
    """Find all facts with a given predicate"""
    return [f for f in facts if f['predicate'] == predicate]

def find_facts_by_subject(subject_id):
    """Find all facts for a given subject entity"""
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

def get_capabilities():
    """Get list of all unique capabilities from entities"""
    capabilities = set()
    for entity in entities:
        capability = entity.get('attributes', {}).get('capability')
        if capability:
            capabilities.add(capability)
    return sorted(list(capabilities))

def get_domain_statistics(domain):
    """Get statistics for a specific domain"""
    return next((pack for pack in packs_metadata if pack['domain'] == domain), None)
```

**Usage in Subsequent Phases:**
```python
if fact_graph_loaded:
    # Use fact graph data
    # Get all capabilities for iteration
    capabilities = get_capabilities()

    # For a specific capability, filter entities
    capability_entities = find_entities_by_capability('OrderManagement')

    # Get business rules for the capability
    entity_ids = [e['id'] for e in capability_entities]
    business_rules = [f for f in facts if f['subject_id'] in entity_ids and f['predicate'] == 'business_rule']

    # Get validations for the capability
    validations = [f for f in facts if f['subject_id'] in entity_ids and f['predicate'] in ['validates', 'is_required', 'max_length']]

    # Get workflows for the capability
    workflows = [f for f in facts if f['subject_id'] in entity_ids and f['predicate'] in ['state_transition', 'process_step']]
else:
    # Fallback to direct code analysis
    # ... original grep/glob commands ...
```

### Phase 1: Initial Discovery (Quick exploration)
- Review the Executive Summary file if it exists (legacylift-docs/00-Executive-Summary.md) and other files in the legacylift-docs folder
- Scan repository structure
- If fact-graph loaded:
  - Use `get_capabilities()` to identify all core capabilities
  - For the target capability, use `find_entities_by_capability()` to get all relevant entities
  - Quick inventory: controllers, services, validators, models for this capability
- If no fact-graph:
  - Search for code relevant to the core capability that is being analyzed using Grep/Glob

### Phase 2: Business Logic Analysis (Domain understanding)

**If fact-graph loaded:**
- **Use Cases**: Extract from endpoints and controllers filtered by capability
  ```python
  # Get all endpoints for this capability
  capability_entities = find_entities_by_capability(target_capability)
  endpoints = [e for e in capability_entities if e['type'] == 'endpoint']
  controllers = [e for e in capability_entities if e['type'] == 'controller']

  # For each endpoint, get HTTP method and route
  for endpoint in endpoints:
      endpoint_id = endpoint['id']
      http_methods = [f for f in facts if f['subject_id'] == endpoint_id and f['predicate'] == 'http_method']
      route = endpoint.get('attributes', {}).get('route', '')
      # Use case derived: HTTP_METHOD route_path (citation: file:line)
  ```

- **Business Rules**: Extract from business_rule facts
  ```python
  # Get all business rules for entities in this capability
  entity_ids = [e['id'] for e in capability_entities]
  business_rules = [f for f in facts if f['subject_id'] in entity_ids and f['predicate'] == 'business_rule']

  for rule in business_rules:
      entity = get_entity_by_id(rule['subject_id'])
      rule_description = rule['object']
      evidence = rule['evidence'][0]  # file:line for citation
      # Document: BR-XXX: rule_description [📄](evidence)
  ```

- **Workflows**: Extract from state_transition and process_step facts
  ```python
  # Get all workflow facts for entities in this capability
  state_transitions = [f for f in facts if f['subject_id'] in entity_ids and f['predicate'] == 'state_transition']
  process_steps = [f for f in facts if f['subject_id'] in entity_ids and f['predicate'] == 'process_step']

  # Build workflow diagrams
  for transition in state_transitions:
      entity = get_entity_by_id(transition['subject_id'])
      from_state = transition['attributes'].get('from_state')
      to_state = transition['attributes'].get('to_state')
      condition = transition['attributes'].get('condition')
      # Document workflow: entity transitions from_state → to_state when condition
  ```

- **Functional Requirements**: Derive from controller methods, service methods, and validation logic
  ```python
  # Get services and their methods
  services = [e for e in capability_entities if e['type'] == 'service']
  for service in services:
      service_id = service['id']
      methods = [f for f in facts if f['subject_id'] == service_id and f['predicate'] == 'has_method']
      # Each method represents a functional requirement
  ```

- **Validation Logic**: Extract from validation facts
  ```python
  # Get all validation facts for entities in this capability
  required_facts = [f for f in facts if f['subject_id'] in entity_ids and f['predicate'] == 'is_required']
  max_length_facts = [f for f in facts if f['subject_id'] in entity_ids and f['predicate'] == 'max_length']
  validates_facts = [f for f in facts if f['subject_id'] in entity_ids and f['predicate'] == 'validates']

  # Document validation rules with citations from evidence
  for fact in validates_facts:
      entity = get_entity_by_id(fact['subject_id'])
      property_name = fact['object']
      validation_rule = fact.get('attributes', {}).get('rule')
      evidence = fact['evidence'][0]
  ```

**If no fact-graph:**
- Analyze functionality to determine and document ALL use cases for the Core Capability (use Task/Explore)
- Extract and document ALL business rules for the Core Capability (grep for validation patterns)
- Identify and document ALL business workflows for the Core Capability (read service/controller code)
- Document ALL functional requirements for the Core Capability
- Document validation logic for the Core Capability

### Domain Ordering Strategy

**Before writing the "Functional Requirements by Domain" section, determine the correct ordering of domains within the capability document.** Do NOT use arbitrary or alphabetical order. Instead, analyze data dependencies between sub-domains and order them by business process flow.

**Ordering Heuristic** (apply within the capability's scope):

1. **Entry points / Triggers first**: The sub-domain that initiates the process (e.g., claim ingestion, batch processing, incoming webhook) comes first.
2. **Processing stages in pipeline order**: Sub-domains that process data in sequence should follow that sequence (e.g., discovery → suggestion generation → filtering → pricing → selection → recommendation).
3. **Consumer-facing output last**: The sub-domain that produces the final user-visible result comes last.
4. **Supporting sub-domains at the end**: Cross-cutting or auxiliary sub-domains (caching, auditing) come after the main pipeline.

**How to apply**:
1. After Phase 2, list all identified sub-domains for this capability
2. Identify which sub-domain is the trigger/entry point for the business process
3. Trace the data flow from trigger to output — this gives you the natural ordering
4. Use Mermaid sequence/flow diagrams (if generated) to confirm the ordering
5. Number domains in this order when writing Domain 1, Domain 2, Domain 3, etc.

**Example**: For a capability with Claim Processing, Opportunity Discovery, Suggestion Engine, Filtering, Pricing, Price Selection, and Recommendations sub-domains:
- Domain 1: Claim Processing (trigger)
- Domain 2: Opportunity Discovery (starts from a claim)
- Domain 3: Suggestion Engine (invoked by discovery)
- Domain 4: Filtering (filters suggestions)
- Domain 5: Pricing/Adjudication (prices filtered suggestions)
- Domain 6: Price Selection (selects best from priced results)
- Domain 7: Recommendations (final consumer-facing output)

### Phase 3: Document Generation with Inline Citations (Synthesis with Provenance)

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
- Verify accuracy against codebase
- Ensure consistency across documents
- Validate all citations point to actual implementations
- Check diagram accuracy
- Add table of contents
- Ensure NO sections lack citations

### Final Step
**Remove the marker** when writing the last section:
- **old_string**: `<!-- MORE CONTENT TO FOLLOW -->`
- **new_string**: `[FINAL SECTION CONTENT]\n\n---\n\n*Generated By LegacyLift AI by CapTech*\n\n*Generated on: {GENERATED_DATETIME}*`
- Replace `{GENERATED_DATETIME}` with the current date and time in ISO 8601 format (e.g., `2026-02-16T14:30:45Z`)

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
   - First 1-2 functional requirement domains (e.g., Point Creation, Survey Management)
   - Add marker at the end: `<!-- MORE CONTENT TO FOLLOW -->`

Example:
```markdown
# Business Rules & Requirements: Pipeline Point Infrastructure Management
[front matter...]
## Functional Requirements by Domain
### Domain 1: Point Creation and Setup
[all requirements with citations...]
### Domain 2: Geographic Survey Management
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
7. **Use Cases & User Stories** (5-10 representative examples)
8. **Related Documents + Footer** (final section, remove marker)

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
7. Edit: Replace marker with Related Docs + footer (no marker)
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
    ├── 03-BUSINESS-RULES-AND-REQUIREMENTS-CORE_CAPABILITY_NAME.md (there should be multiple of these)
    ├── 04-INTEGRATION-AND-API-GUIDE.md
    └── 05-QUICK-REFERENCE.md

When using this skill, you can specify the output directory using the `output_dir` parameter. For example:
```
/legacylift-classic:detailed-req-documenter output_dir=repos/my_project/legacylift-docs
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
   - Phase 0: Load Fact Graph (if available)
   - Phase 1: Initial Discovery
   - Phase 2: Business Logic Analysis (using fact-graph if loaded)
   - Phase 3: Document Generation (with inline citations as you write)
   - Phase 4: Review & Polish

3. **Execute Systematically**
   - **Phase 0**: Load fact-graph if available (provides 85% of code information needed)
   - Use fact-graph data for entity/fact queries when available
   - Use Tasks to strategically launch exploration agents when fact-graph unavailable or for supplementary analysis
   - Gather information in parallel where possible
   - Build comprehensive understanding
   - Reference templates for consistent structure
   - **For Phase 3 - Generate documents with inline citations**:
     * Break each document into logical sections
     * For each section, create a detailed todo list with tasks like:
       - "Search for [Technology X] evidence" (use fact-graph if loaded, Task/Explore otherwise)
       - "Write [Section Y] with inline citations"
       - "Validate [Section Y] citations"
     * BEFORE writing prose, gather ALL relevant source files:
       - If fact-graph loaded: Query entities/facts for citations from evidence fields
       - If no fact-graph: Launch Task/Explore agents to find source files
     * Gather file paths and line numbers for citations
     * Write section WITH citations inline (never write without citing)
     * Use Write tool to create section with complete citations from the start
     * Validate every claim has a citation before marking section complete
     * Move to next section only after current section is fully cited
     * **Never write a sentence without immediately adding its citation**
     * **Pattern: Query/Search → Gather → Write-with-Citations → Validate → Next Section**
   - Cross-validate findings against codebase

4. **Deliver Complete Documentation**
   - 03-BUSINESS-RULES-AND-REQUIREMENTS-{CAPABILITY}.md for each core capability
   - Placed in `legacylift-docs/` directory (or specified location)
   - Following proven template structures
   - With Mermaid diagrams, exhaustive inline source citations, and cross-links
   - **Every substantive claim backed by verifiable source code references from initial writing**
   - **Citations sourced from fact-graph evidence fields when available (file:line from entity locations)**
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

This skill uses one template:

| Template File | Purpose | Usage |
|---------------|---------|-------|
| **[03-BUSINESS-RULES-AND-REQUIREMENTS.md](./templates/03-BUSINESS-RULES-AND-REQUIREMENTS.md)** | Structure for detailed requirements per core capability | Guides functional requirements, business rules, use cases for a specific domain |

### LegacyLift Documentation Ecosystem

This skill is part of the comprehensive LegacyLift documentation suite. Here's the complete set of documents available:

| Prefix | Document | Generated By | Description |
|--------|----------|--------------|-------------|
| **Core Documentation Suite** ||||
| 00 | EXECUTIVE-SUMMARY | exec-summary-generator | High-level overview for all stakeholders |
| 01 | SYSTEM-ARCHITECTURE | si-documenter | Technical architecture deep dive |
| 02 | DATA-MODEL-AND-RELATIONSHIPS | data-documenter, database-layer-documenter | Data structures and relationships |
| 03 | [BUSINESS-RULES-AND-REQUIREMENTS](./templates/03-BUSINESS-RULES-AND-REQUIREMENTS.md) ⭐ | business-documenter, **detailed-req-documenter** | Functional requirements and rules |
| 04 | INTEGRATION-AND-API-GUIDE | si-documenter | API documentation and integration patterns |
| 05 | QUICK-REFERENCE | si-documenter | Glossary and quick lookups |
| **Extended Documentation & Analysis** ||||
| 06 | TABLE-VALIDATION-* | table-validation | ORM mapping validation reports |
| 07 | DOCUMENTATION-ACCURACY-REPORT | documentation-review | Documentation accuracy validation |
| 08 | USE-CASES-{DOMAIN} | use-case-generator | Comprehensive use case documentation |
| 09 | CITATION-VALIDATION-REPORT | citation-validator | Citation correctness validation |
| 10 | GAP-ANALYSIS-REPORT | gap-analyzer | Documentation-code gap analysis |

⭐ = Generated by this skill (creates 03-BUSINESS-RULES-AND-REQUIREMENTS-{CORE_CAPABILITY_NAME}.md for each core capability)

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
