---
name: user-story-generator
description: Analyzes use case documentation and source code for a specific domain and generates a comprehensive, exhaustive set of user stories organized into epics, following industry best practices.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, BashOutput, Task, TodoWrite, Skill, WebFetch
---

# User Story Generator

This skill analyzes use case documentation and source code for a specific domain and generates a comprehensive, exhaustive set of user stories organized into epics, suitable for product managers, development teams, and modernization projects.

## Instructions

The user-story-generator skill systematically analyzes use case documentation and source code using the "Skill Execution" and "Documentation Process" described below, and produces a single file:

1. **11-USER-STORIES-{DOMAIN}.md** - Comprehensive user story documentation with epics for the specified domain (40-50 min read)

## Examples

```
Generate user stories for the CLAIMS domain using the user-story-generator skill.
```

```
Use the user-story-generator skill to create user stories for Access Control.
```

```
/legacylift-classic:user-story-generator domain=CLAIMS input_doc=legacylift-docs/08-USE-CASES-Claims-Management.md
```

--- 

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

## Documentation Process

The skill follows a systematic 5-phase approach:

**⚠️ CRITICAL RULE #1: ALL stories must be fully detailed. NEVER create summaries, samples, or placeholders. If you identify 155 stories, you MUST write all 155 stories with complete acceptance criteria and citations. NO EXCEPTIONS.**

**⚠️ CRITICAL RULE #2: Citations are NOT a post-processing step. Every user story acceptance criterion, technical implementation note, and business rule must be cited AS YOU WRITE IT. Never write prose first and add citations later - this leads to poor quality citations and extra work.**

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

When fact-graph is loaded, use it to accelerate implementation discovery:

```python
if fact_graph_loaded:
    # Get all endpoints for use case identification
    endpoints = find_entities_by_type('endpoint')

    # Get all controllers and services
    controllers = find_entities_by_type('controller')
    services = find_entities_by_type('service')

    # Get validation rules for acceptance criteria
    validation_facts = find_facts_by_predicate('validates')
    required_facts = find_facts_by_predicate('is_required')

    # Get business rules
    business_rules = find_facts_by_predicate('business_rule')

    # Get controller->service relations for traceability
    calls_relations = find_relations_by_type('calls')

    # Use evidence fields for citations
    for entity in endpoints:
        file_path = entity['file']
        line_range = entity['line_range']
        # Citation: [📄](file_path:line_range[0]-line_range[1])
else:
    # Fallback to Task/Explore for implementation discovery
    # ... original grep/glob commands ...
```

**Benefits:**
- ✅ Fast access to all controllers, services, endpoints without grep
- ✅ Pre-extracted validation rules and business rules
- ✅ Evidence fields provide file:line for citations
- ✅ Relations show controller→service→repository traceability
- ✅ Dramatically reduces citation work

### Phase 1: Input Discovery & Analysis (Understand the domain)
- Identify and read the use case document(s) for the domain
- Identify and read the business requirements document(s) for the domain
- Review existing user stories if present in the documentation
- Identify all actors/personas from use cases
- Identify all functional requirements for the domain
- Identify all workflows and user interactions
- Map out the domain capabilities and features
- Understand technical implementation patterns
- **Identify major themes/workflows that will become epics**

### Phase 2: Epic & User Story Identification (Extract all scenarios)

#### Epic Identification:
- **Analyze Use Cases for Major Workflows**: Group related use cases into themes
  - Example: UC-001 through UC-005 about "Claim Creation" → Epic: "Claim Creation and Setup"
  - Example: UC-006 through UC-012 about "Claim Assessment" → Epic: "Claim Assessment and Adjudication"
- **Identify Entity Lifecycles**: Each major entity often maps to an epic
  - Example: Customer lifecycle → Epic: "Customer Onboarding and Management"
  - Example: Contract lifecycle → Epic: "Contract Lifecycle Management"
- **Identify Cross-Cutting Concerns**: Common themes across use cases
  - Example: All authentication/authorization stories → Epic: "Security and Access Control"
  - Example: All reporting stories → Epic: "Reporting and Analytics"
- **Target**: 5-8 epics per domain, each representing a major capability or workflow

#### User Story Identification:
- **Use Case to User Story Mapping**: For each use case:
  - Identify the main actor/persona
  - Break use case into atomic user stories (one goal per story)
  - Extract preconditions as setup/dependency stories
  - Extract postconditions as verification stories
  - Extract alternative flows as error handling stories
  - Extract business rules as validation stories
- **Actor-Based Analysis**: For each actor/persona identified:
  - What are their core workflows
  - What are their pain points
  - What information do they need
  - What actions do they need to perform
  - What decisions do they need to make
- **CRUD Analysis**: For each entity in the domain:
  - Create stories
  - Read/Query stories (various filters and views)
  - Update stories
  - Delete/Inactivate stories
- **Integration Analysis**: For each integration point:
  - API endpoint stories
  - Data synchronization stories
  - Error handling stories
  - Monitoring stories
- **Non-Functional Requirements**: Extract stories for:
  - Performance requirements
  - Security requirements
  - Audit/compliance requirements
  - Error handling and validation
  - User experience improvements
- **Create Comprehensive List**: Enumerate ALL user stories (100-200+ typical)
- **Assign to Epics**: Map each user story to its parent epic

**⚠️ CRITICAL: This list of ALL user stories is what you MUST document. If you identify 155 stories, you must write 155 stories in full detail. NEVER write summaries like "US-XXX through US-YYY: Additional capabilities" - every single story must have complete acceptance criteria, technical implementation, business rules, related stories, and priority/sizing.**

### Phase 3: User Story Elaboration (Detail EVERY story - No Summaries Allowed)

**⚠️ CRITICAL: You must elaborate EVERY SINGLE user story identified in Phase 2. If Phase 2 identified 155 stories, then Phase 3 must elaborate all 155 stories with full detail. NEVER create summary placeholders like "Additional stories for..." or "US-XXX through US-YYY cover..."**

For each user story identified (ALL of them):
- **Search for Implementation Evidence**:
  - **If fact-graph loaded**: Query entities, facts, and relations for:
    - Endpoints: `find_entities_by_type('endpoint')`
    - Controllers: `find_entities_by_type('controller')`
    - Services: `find_entities_by_type('service')`
    - Validation facts: `find_facts_by_predicate('validates')`, `find_facts_by_predicate('is_required')`
    - Business rules: `find_facts_by_predicate('business_rule')`
    - Relations: `find_relations_by_type('calls')` for controller→service traceability
    - Use evidence fields from entities/facts for file:line citations
  - **If fact-graph NOT loaded**: Use Task/Explore to find:
    - Controller methods that implement the story
    - Service/manager methods with business logic
    - Validation logic and business rules
    - UI components (JSP, React, Angular, etc.) for the story
    - Database models and entities involved
    - API endpoints that support the story
- **Gather Citations**: Collect file paths and line numbers BEFORE writing (from fact-graph evidence or file reads)
- **Write User Story WITH Citations**: Include:
  - User story in standard format: "As a [persona], I want [functionality], so that [business value]"
  - Acceptance criteria with citations to validation logic
  - Technical implementation notes with citations to controllers/services
  - Related user stories (dependencies)
  - Business rules referenced with citations
  - Priority/size estimation based on implementation complexity

### Phase 4: Document Generation with Inline Citations (Synthesis with Provenance)

**CRITICAL: Citations must be generated inline as you write, not added later.**

1. **Write epic-by-epic with immediate citation**:
   - Identify epics from Phase 2 analysis
   - For each epic, write all user stories in that epic
   - BEFORE writing each story, search for ALL implementation evidence
   - Write the user story WITH citations inline from the start
   - Never write an acceptance criterion without immediately adding its citation

2. **Citation-First Writing Workflow**:
   ```
   For each epic:
     For each user story in epic:
       a) Identify the user story (e.g., "Administrator Creates New Claim")
       b) Search NOW for controller methods, validation, business logic, UI
       c) Write story header WITH citation to main implementation
       d) Write acceptance criteria WITH citations to validation/business rules
       e) Write technical notes WITH citations to controllers/services/UI
       f) Write related stories WITH links to dependent stories
       g) Move to next user story
     Move to next epic
   ```

3. **User Story Generation Process**:
   - **Plan**: List all epics and user stories to document for the domain
   - **Search**: Use Task/Explore to find implementation for current user story
   - **Write**: Compose user story with inline citations for every detail
   - **Validate**: Verify every acceptance criterion has a citation before moving to next story

4. **Citation Standards** (apply during writing):
   - Story description → cite main controller method or UI component
   - Acceptance criteria → cite validation methods, business rules, or test cases
   - Technical implementation → cite controller methods, service methods, database entities
   - UI behavior → cite JSP files, React components, or JavaScript files
   - Business rules → cite validation methods, business logic, or rule engines
   - Integration → cite API endpoints, message handlers, or integration services

5. **Citation Format**:
   - Inline: `acceptance criterion [📄](path/to/file.ext:line)`
   - Explicit: `technical note [source](path/to/file.ext:line-range)`
   - Multiple sources: `criterion [1](path1:line) [2](path2:line)`

6. **Quality Criteria** (verify as you write each user story):
   - Every acceptance criterion has a citation to where it's validated or implemented
   - Every technical note has a citation to the implementation
   - Every business rule reference has a citation to the validator or business logic
   - UI-related stories cite UI components (JSP, React, etc.)
   - API stories cite controller endpoints
   - Citations use specific line numbers, not vague references

**Example of Citation-First Writing:**

❌ **WRONG - Writing first, citing later:**
```
Epic 1: Claim Management

US-001: As an Administrator, I want to create a new claim, so that I can process customer requests.

Acceptance Criteria:
- Administrator can access claim creation form
- All required fields must be provided
- System validates claim data
- System creates claim record
[Later: try to find and add citations]
```

✅ **CORRECT - Citing inline during initial writing:**
```
For epic "Claim Management" and user story "Administrator Creates Claim":
1. Search NOW: Find ClaimController.CreateClaim, validation, UI components
2. Gather evidence: ClaimController.cs:71-76, ClaimManager.cs:138-188, claimForm.jsp:45
3. Write WITH citations:

## Epic 1: Claim Creation and Setup [📄](ClaimController.cs:1)

### US-001: Create New Claim [📄](ClaimController.cs:71-76)

**Story**: As an Administrator, I want to create a new claim, so that I can process customer requests.

**Acceptance Criteria**:
- Administrator can access claim creation form [📄](claimForm.jsp:45-67)
- All required fields (claim number, customer, date) must be provided [📄](ClaimDto.cs:17-25)
- System validates claim data against business rules [📄](ClaimManager.cs:140-145)
- System creates claim record in database [📄](ClaimManager.cs:147-149)
- User receives success confirmation message [📄](ClaimController.cs:74)

**Technical Implementation**:
- Controller: ClaimController.CreateClaim() [📄](ClaimController.cs:71-76)
- Service: ClaimManager.CreateClaim() [📄](ClaimManager.cs:138-188)
- Validation: ClaimValidator.ValidateCreate() [📄](ClaimValidator.cs:42-78)
- UI: claimForm.jsp [📄](claimForm.jsp:45-120)

**Business Rules**: BR-CLAIM-001 [📄](ClaimValidator.cs:42), BR-CLAIM-002 [📄](ClaimValidator.cs:58)

**Related Stories**: US-002 (Add Claim Details), US-003 (Attach Documents)

**Priority**: High | **Size**: Medium (5 story points)
```

### Phase 5: Review & Polish (Quality assurance)
- Verify all user stories are comprehensive and cover the domain
- Ensure consistency across user stories and epics
- Validate all citations point to actual implementations
- Check that all personas are properly identified
- Ensure story dependencies are correctly identified
- Ensure NO user stories lack citations
- Validate user story numbering and organization
- Check that stories are atomic (single responsibility)
- Verify acceptance criteria are testable
- Ensure epic descriptions accurately summarize contained stories

---

## Incremental Document Writing Process

**⚠️ MANDATORY: All user story documentation must be written incrementally to manage context efficiently and avoid token limits.**

### Why Incremental Writing?
- Long documents (40-50 min read) can exceed context windows if written all at once
- Reading the full file before each append wastes tokens
- Incremental writing allows indefinite document length
- More efficient and reliable for comprehensive documentation

### Initial Setup

1. **Create the initial document** with:
   - Front matter (title, audience, reading time, table of contents)
   - Domain Overview section
   - Epic Overview section (list all epics)
   - First epic with 3-5 user stories
   - Add marker at the end: `<!-- MORE CONTENT TO FOLLOW -->`

Example:
```markdown
# User Stories: Claims Management
[front matter...]
## Epic Overview
[list of all 6 epics...]
## Epic 1: Claim Creation and Setup
### US-001: Create New Claim
[full user story with citations...]
### US-002: Add Claim Details
[full user story with citations...]
<!-- MORE CONTENT TO FOLLOW -->
```

### For Each Additional Section

2. **Use the Edit tool** to replace the marker with new content:
   - **old_string**: `<!-- MORE CONTENT TO FOLLOW -->`
   - **new_string**: `[NEW USER STORIES OR EPIC SECTION]\n\n<!-- MORE CONTENT TO FOLLOW -->`

3. **DO NOT read the full file** before appending - the Edit tool will find and replace the marker

4. **For each user story you write:**
   - Search for implementation evidence FIRST using Task/Explore or direct file reads
   - Gather all file paths and line numbers BEFORE writing prose
   - Write the user story WITH inline citations as you compose each acceptance criterion
   - Never write an acceptance criterion or technical note without immediately adding its citation
   - Replace the marker and continue to the next user story

### Writing Pattern for Each User Story

```
For each epic:
  For each user story in epic:
    1. Search NOW: Find controller, service methods, validation logic, UI components
    2. Gather citations: Collect file:line references
    3. Write WITH citations:
       - Story title [📄](main-implementation:line)
       - As a [persona] [📄](authorization:line)
       - Acceptance Criterion 1 [📄](validation:line)
       - Acceptance Criterion 2 [📄](business-logic:line)
       - Technical Implementation [📄](controller:line) [📄](service:line) [📄](ui:line)
       - Business Rules [📄](validator:line)
       - Related Stories (links to US-XXX)
       - Priority/Size estimation
    4. Replace marker with: user story content + marker
    5. Move to next user story
```

### Final Step

5. **Remove the marker** when writing the last section (Summary, Related Documents, Footer)
   - **old_string**: `<!-- MORE CONTENT TO FOLLOW -->`
   - **new_string**: `[FINAL SECTION CONTENT]\n\n---\n\n*Generated By LegacyLift AI by CapTech*`

### Key Rules

- ✅ Write epic-by-epic, story-by-story incrementally
- ✅ Replace the marker each time using Edit tool (don't read the whole file)
- ✅ Generate citations DURING writing (not after)
- ✅ Search for evidence BEFORE writing each user story
- ✅ Use Edit tool with exact marker text for find/replace
- ❌ DO NOT read the entire file between user stories
- ❌ DO NOT write acceptance criteria first and add citations later
- ❌ DO NOT skip the marker (always add it until the final section)

### Example Workflow

```
1. Write: Front matter + Epic Overview + Epic 1 (US-001 to US-005) + marker
2. Edit: Replace marker with Epic 1 continued (US-006 to US-010) + marker
3. Edit: Replace marker with Epic 2 (US-011 to US-020) + marker
4. Edit: Replace marker with Epic 3 (US-021 to US-030) + marker
5. Edit: Replace marker with Epic 4 (US-031 to US-040) + marker
6. Edit: Replace marker with Summary + Related Documents + footer (no marker)
```

### Token Efficiency

This approach:
- Keeps context usage minimal (only marker location needed, not full file)
- Allows documents of any length to be created
- Maintains citation quality throughout
- Prevents context window exhaustion
- Enables you to write 100+ user stories without issues

---

## Key Features

### 🎯 **Exhaustive Coverage - EVERY Story Fully Detailed**

**⚠️ CRITICAL: NEVER create summaries, samples, or representative stories. EVERY user story identified must be written in full detail with complete acceptance criteria and citations.**

Systematically identifies and FULLY DETAILS ALL user stories for a domain:
- Core functional stories from use cases (typically 60-80%)
- CRUD operations for all entities (typically 10-15%)
- Data validation and business rule stories (typically 5-10%)
- Error handling and edge case stories (typically 5-10%)
- Integration and API stories (typically 5-10%)
- Non-functional requirement stories (performance, security, audit) (typically 5-10%)
- User experience and usability stories (typically 5%)

**If 155 stories are identified, then 155 stories must be written. If 200 stories are identified, then 200 stories must be written. NEVER abbreviate or summarize.**

### 📊 **Epic Organization**
User stories organized into domain-specific epics:
- 5-8 epics per domain typical
- 10-30 user stories per epic typical
- Epics derived from use case analysis and entity lifecycles
- Each epic represents a major capability or workflow
- Clear epic descriptions with business value statements

### 👥 **Persona-Centered Stories**
User stories written for specific personas:
- Internal users (administrators, analysts, operators)
- External users (customers, partners, vendors)
- System administrators (monitoring, configuration)
- API consumers (downstream systems, integrations)
- Clear role identification and permissions

### 📋 **Standard User Story Format**
Each user story includes:
- **ID**: Unique identifier (US-001, US-002, etc.)
- **Title**: Concise story description
- **Story**: As a [persona], I want [functionality], so that [business value]
- **Acceptance Criteria**: Testable criteria (with citations)
- **Technical Implementation**: Controller, service, UI, database (with citations)
- **Business Rules Referenced**: Links to validators and business logic (with citations)
- **Related Stories**: Dependencies and related stories (with US-XXX links)
- **Priority**: High/Medium/Low based on business value
- **Size**: Story point estimation based on implementation complexity

### 🔗 **Deep Code Integration**
Every user story element includes source code references:
- File paths with line numbers
- Direct links to controller methods, services, validators
- UI component citations (JSP, React, Angular, Vue, etc.)
- Database model citations
- Verifiable against actual codebase

### 🔄 **Traceability**
Clear traceability between:
- User stories and epics
- User stories and use cases
- User stories and functional requirements
- User stories and implementation code
- User stories and business rules
- User stories and test cases
- Dependencies between related stories

## What Gets Analyzed

The skill examines:

### Use Case Documents
- ✅ All use cases for the domain
- ✅ Actor interactions and workflows
- ✅ Preconditions and postconditions
- ✅ Main flows and alternative flows
- ✅ Business rules and validation

### Business Requirements Documents
- ✅ Functional requirements by domain
- ✅ Business rules and validation logic
- ✅ User workflows and processes
- ✅ Compliance and security requirements
- ✅ Non-functional requirements

### Source Code
- ✅ Controller methods and endpoints
- ✅ Service/manager business logic
- ✅ Validation logic and rules
- ✅ Authorization and permission checks
- ✅ UI components (JSP, React, Angular, Vue, etc.)
- ✅ Database models and entities
- ✅ Error handling and exceptions
- ✅ Integration points and APIs

### Architecture
- ✅ Actor roles and permissions
- ✅ Integration points
- ✅ External system interactions
- ✅ Data flows and transformations

## Output Quality Standards

Generated user story documentation includes:

✅ **Clear Structure** - Table of contents, epic sections, story groupings
✅ **Estimated Reading Time** - Help readers allocate time (40-60 min typical, longer for domains with 200+ stories)
✅ **Target Audience** - Who should read this document
✅ **Epic Organization** - 5-8 epics per domain with clear descriptions
✅ **100% Complete Coverage** - ALL user stories for the domain FULLY DETAILED (100-200+ stories typical)
✅ **ZERO Summaries** - NO summary placeholders, NO "Additional capabilities", NO "US-XXX through US-YYY"
✅ **Persona Identification** - Clear identification of all actors and personas
✅ **Standard Format** - Consistent "As a, I want, So that" format for every story
✅ **Testable Acceptance Criteria** - Clear, verifiable criteria for each story
✅ **Exhaustive Citations** - **Every** acceptance criterion, technical note, and business rule has inline source code citations with precise file paths and line numbers
✅ **Verifiable Claims** - All criteria can be validated by following citation links to actual implementation code
✅ **Business Rules Cross-Reference** - Links to validation logic and business rules
✅ **Related Stories** - Dependencies and relationships between stories with US-XXX links
✅ **Traceability** - Clear mapping to use cases, requirements, and implementation
✅ **Atomic Stories** - Each story represents single, testable functionality
✅ **Priority and Sizing** - Business priority and complexity estimation for planning
✅ **Document Footer** - Document MUST end with the footer: `---\n\n*Generated By LegacyLift AI by CapTech*`

## Example Output Structure

```
project-root/
└── legacylift-docs/
    ├── 00-EXECUTIVE-SUMMARY.md
    ├── 01-SYSTEM-ARCHITECTURE.md
    ├── 02-DATA-MODEL-AND-RELATIONSHIPS.md
    ├── 03-BUSINESS-RULES-AND-REQUIREMENTS.md
    ├── 03-BUSINESS-RULES-AND-REQUIREMENTS-Claims-Management.md
    ├── 04-INTEGRATION-AND-API-GUIDE.md
    ├── 08-USE-CASES-CLAIMS.md
    ├── 11-USER-STORIES-CLAIMS.md  ← Generated by this skill (150+ stories in 6 epics)
    └── 11-USER-STORIES-ACCESS-CONTROL.md  ← Generated by this skill (80+ stories in 5 epics)
```

## Technical Implementation

This skill uses Claude Code's advanced capabilities:

- **Fact Graph Integration**: Loads pre-generated fact graph (Phase 0) for fast access to entities, relations, and facts with evidence
- **Task Tool**: Launches specialized exploration agents for thorough analysis (when fact-graph not available)
- **Parallel Analysis**: Analyzes multiple aspects concurrently
- **Code Search**: Grep and Glob for finding implementations (fallback when fact-graph unavailable)
- **File Reading**: Deep inspection of use cases, requirements docs, and source files
- **Template System**: Consistent user story documentation structure
- **Citation Validation**: Verify all citations point to actual code
- **Incremental Writing**: Efficient document generation using marker pattern

**Fact-Graph Benefits:**
- ✅ Pre-extracted controllers, services, endpoints eliminate grep operations
- ✅ Validation rules and business rules already extracted with evidence
- ✅ Evidence fields provide file:line for citations automatically
- ✅ Relations show controller→service traceability for technical implementation notes
- ✅ Dramatically faster citation gathering through O(1) lookups

## Success Criteria

Documentation is considered complete when:

✅ All epics for the domain are identified (5-8 typical)
✅ **ALL user stories for the domain are identified and FULLY DOCUMENTED (100-200+ stories typical)**
✅ **EVERY story has complete acceptance criteria, technical implementation, business rules, related stories, and priority/sizing**
✅ **ZERO stories are summarized, abbreviated, or represented as "Additional capabilities"**
✅ **If 155 stories identified → 155 stories fully written. If 200 stories identified → 200 stories fully written**
✅ **Every acceptance criterion has inline source code citations with file paths and line numbers (generated during initial writing, not added later)**
✅ **Acceptance criteria cite validation logic, business rules, or test cases**
✅ **Technical notes cite controller/service/UI implementation**
✅ **Business rules cite validators and business logic**
✅ **UI behaviors cite UI components (JSP, React, Angular, etc.)**
✅ **No user story was written without citations - they were integral to the writing process**
✅ All personas are clearly identified with role descriptions
✅ Stories are atomic (single responsibility per story)
✅ Acceptance criteria are testable and specific
✅ Story dependencies are identified with US-XXX links
✅ Stories are organized into logical epics with clear descriptions
✅ Each epic has business value statement
✅ Priority and size estimations provided for planning
✅ Technical accuracy is verified against source code
✅ **Citations can withstand scrutiny - they point to actual implementations**
✅ **Document never required post-processing to add citations - they had them from the start**

## Skill Execution

**⚠️ MANDATORY WORKFLOW: When writing any user story, you MUST:**
1. Search for implementation evidence FIRST using Task/Explore
2. Gather all file paths and line numbers for the user story
3. Write user story WITH citations inline for every acceptance criterion
4. Never write an acceptance criterion without its citation

When this skill is invoked, I will:

1. **Clarify the Context**
   - Identify the domain (e.g., CLAIMS, Access Control, Customer Management)
   - Locate the use case document for the domain
   - Locate the business requirements document for the domain
   - Confirm output directory and file naming convention
   - Ask if there are specific personas or areas of focus

2. **Create Todo List**
   - Phase 0: Load Fact Graph (if available)
   - Phase 1: Input Discovery & Analysis
   - Phase 2: Epic & User Story Identification
   - Phase 3: User Story Elaboration
   - Phase 4: Document Generation (with inline citations as you write)
   - Phase 5: Review & Polish

3. **Execute Systematically**
   - Load fact graph if available (Phase 0)
   - Read use case documentation thoroughly
   - Read business requirements documentation
   - If fact-graph loaded: Query entities/facts for implementation code
   - If fact-graph NOT loaded: Use Task/Explore to find all implementation code for the domain
   - Identify all personas, functional requirements, and workflows
   - **Identify 5-8 epics from major workflows and entity lifecycles**
   - Create comprehensive list of user stories (100-200+ typical) mapped to epics
   - **For Phase 4 - Generate document with inline citations**:
     * Break document into epic sections
     * For each epic:
       - Write epic description with business value
       - For each user story in epic:
         - Search for implementation evidence BEFORE writing
         - Gather all file paths and line numbers
         - Write user story WITH citations inline from the start
         - Validate every acceptance criterion has a citation before moving to next story
     * **Never write an acceptance criterion without immediately adding its citation**
     * **Pattern: Search → Gather → Write-with-Citations → Validate → Next Story**
   - Cross-validate against source code

4. **Deliver Complete Documentation**
   - 11-USER-STORIES-{DOMAIN}.md in markdown format
   - Placed in `legacylift-docs/` directory (or specified location)
   - Following proven template structure
   - With 5-8 epics and 100-200+ user stories
   - **EVERY SINGLE user story fully detailed - NO summaries, NO samples, NO "additional capabilities" placeholders**
   - With exhaustive inline source citations (200+ citations typical)
   - **Every acceptance criterion backed by verifiable source code references from initial writing**
   - **No user story written without citations - they're integral to the writing process**
   - **If you identified 155 stories in Phase 2, then the document contains 155 fully-detailed stories**
   - Ready for immediate use by development teams for modernization

   When using this skill, you can specify parameters:
   ```
   /legacylift-classic:user-story-generator domain=CLAIMS input_doc=path/to/use-cases.md output_dir=legacylift-docs
   ```
   - `domain`: Required - the domain name (e.g., CLAIMS, AccessControl, CustomerManagement)
   - `input_doc`: Optional - path to use case document to analyze
   - `output_dir`: Optional - output directory (defaults to `legacylift-docs/` in analyzed repo)

5. **Provide Summary**
   - Number of epics identified (5-8 typical)
   - Number of user stories documented per epic
   - Total user stories (100-200+ typical)
   - Personas identified
   - Coverage analysis (what was documented, any gaps)
   - Recommendations for development priorities and sprint planning

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


## Supporting Files & Templates

This skill uses supporting files in the `templates/` directory to ensure consistent, high-quality documentation output.

### Template Structure

| Template File | Purpose | Usage |
|---------------|---------|-------|
| **[11-USER-STORIES-TEMPLATE.md](./templates/11-USER-STORIES-TEMPLATE.md)** | Structure for user story docs | Guides story organization, epic structure, format, and content |

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
| 06 | TABLE-VALIDATION-* | table-validation | ORM mapping validation reports |
| 07 | DOCUMENTATION-ACCURACY-REPORT | documentation-review | Documentation accuracy validation |
| 08 | USE-CASES-{DOMAIN} | use-case-generator | Comprehensive use case documentation |
| 09 | CITATION-VALIDATION-REPORT | citation-validator | Citation correctness validation |
| 10 | GAP-ANALYSIS-REPORT | gap-analyzer | Documentation-code gap analysis |
| 11 | [USER-STORIES-{DOMAIN}](./templates/11-USER-STORIES-TEMPLATE.md) ⭐ | **user-story-generator** | Exhaustive user story documentation with epics |

⭐ = Generated by this skill

### How Templates Are Used

During skill execution, I (Claude) will:

1. **Reference Template**: Read the user story template
2. **Extract Structure**: Use the template's sections, headings, and organization
3. **Fill with Analysis**: Replace placeholders with actual epics and user stories from domain analysis
4. **Maintain Consistency**: Ensure all stories follow the same professional format
5. **Adapt as Needed**: Customize epic groupings based on domain specifics

### Template Features

The template includes:

- **Instructional Comments**: HTML comments guiding what content to include
- **Placeholder Syntax**: `{PLACEHOLDER}` markers for domain-specific values
- **Section Organization**: Pre-structured table of contents, epic overview, and epic sections
- **Epic Structure**: Format for epic descriptions with business value
- **User Story Format**: Standardized format for each story
- **Citation Examples**: Examples of proper inline citations
- **Acceptance Criteria Format**: Structure for testable criteria
- **Technical Implementation Section**: Structure for implementation notes
- **Related Stories Section**: Structure for story dependencies
