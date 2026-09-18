---
name: use-case-generator
description: Analyzes business requirements for a domain and generates comprehensive use cases with actors, flows, and acceptance criteria.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, BashOutput, Task, TodoWrite, Skill, WebFetch
---

# Use Case Generator

This skill analyzes business requirements documentation for a specific domain and generates a comprehensive set of use cases suitable for stakeholders, product managers, business analysts, and development teams.

## Instructions

The use-case-generator skill systematically analyzes business requirements documentation and source code using the "Skill Execution" and "Documentation Process" described below, and produces a single file:

1. **08-USE-CASES-{DOMAIN}.md** - Comprehensive use case documentation for the specified domain (30-40 min read)

## Examples

```
Generate use cases for the CLAIMS domain using the use-case-generator skill.
```

```
Use the use-case-generator skill to create use cases for Access Control.
```

```
/legacylift-classic:use-case-generator domain=CLAIMS input_doc=repos/ctcm/ctcm-api/legacylift-docs/03-BUSINESS-RULES-AND-REQUIREMENTS-Claims-Management.md
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

The skill follows a systematic 6-phase approach:

**⚠️ CRITICAL: Citations are NOT a post-processing step. Every use case step, precondition, and postcondition must be cited AS YOU WRITE IT. Never write prose first and add citations later - this leads to poor quality citations and extra work.**

### Phase 0: Load Fact Graph (if available)

**Objective**: Check for and load pre-generated fact graph to avoid redundant code analysis and accelerate use case identification.

**Canonical Reference**: See [FACT-GRAPH-INTEGRATION.md](../FACT-GRAPH-INTEGRATION.md) for the complete Phase 0 specification shared across all skills.

**⚠️ Domain-Scoped Packs**: The fact-graph skill generates domain-scoped pack files (e.g., `core.entities.pack.json`, `points.entities.pack.json`).

**Implementation**:
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

def get_entities_for_domain(target_domain):
    """Get all entities for a specific domain"""
    return [e for e in entities if e.get('attributes', {}).get('domain') == target_domain]

def get_facts_for_entity(entity_id):
    """Get all facts for a specific entity"""
    return [f for f in facts if f['subject_id'] == entity_id]

def get_relations_for_entity(entity_id):
    """Get all relations where entity is source or target"""
    return [r for r in relations if r['source_id'] == entity_id or r['target_id'] == entity_id]
```

**When to Use Fact Graph**:
- ✅ **Use fact-graph** when it exists to:
  - Rapidly identify all endpoints in the domain
  - Find controller methods implementing use cases
  - Extract HTTP methods, parameters, response types
  - Discover validation logic and business rules
  - Map controller→service call chains
  - Find authorization/authentication checks
  - Locate error handling and exception flows
- ❌ **Fallback to direct code analysis** when:
  - Fact-graph doesn't exist
  - Need to read business requirements documents
  - Need to analyze workflow descriptions
  - Need UI component details not captured in fact-graph

**Efficiency Gains**:
- Significantly reduces exploratory grep/glob operations
- Provides complete inventory of endpoints, controllers, services
- Includes pre-extracted validation rules and business logic
- Offers deterministic entity identification for consistent citations
- Enables rapid domain-scoped filtering

### Phase 1: Input Discovery & Analysis (Understand the domain)
- Identify and read the business requirements document(s) for the domain
- Review existing use cases if present in the requirements documents
- Identify all functional requirements for the domain
- Identify all actors/roles mentioned in the domain
- Identify all workflows and business processes
- **If fact-graph loaded**: Query endpoints and controllers for the target domain
  ```python
  if fact_graph_loaded:
      # Get all endpoints for the domain
      domain_endpoints = [e for e in entities
                         if e['type'] == 'endpoint'
                         and e.get('attributes', {}).get('domain') == target_domain]

      # Get all controllers
      controllers = find_entities_by_type('controller')

      # Get HTTP methods and routes for endpoints
      for endpoint in domain_endpoints:
          endpoint_id = endpoint['id']
          http_method_facts = [f for f in facts
                               if f['subject_id'] == endpoint_id
                               and f['predicate'] == 'http_method']
          http_method = http_method_facts[0]['object'] if http_method_facts else 'UNKNOWN'
          route = endpoint.get('attributes', {}).get('route', '')

          # Get authorization requirements
          auth_facts = [f for f in facts
                       if f['subject_id'] == endpoint_id
                       and f['predicate'] in ['requires_auth', 'authorizes_via']]
  else:
      # Fallback: Use Task/Explore to find API endpoints and controller methods
  ```
- **If fact-graph NOT loaded**: Use Task/Explore to find API endpoints and controller methods
- Map out the domain capabilities and features

### Phase 2: Use Case Identification (Extract all scenarios)
- **Systematic Analysis**: For each functional requirement, identify:
  - What user actions trigger this requirement
  - What roles/actors interact with this functionality
  - What are the success scenarios
  - What are the failure/exception scenarios
  - What are the alternative flows
- **Actor-Based Analysis**: For each actor/role identified:
  - What are their goals in this domain
  - What tasks do they need to accomplish
  - What information do they need to access
  - What decisions do they need to make
- **Workflow Analysis**: For each workflow identified:
  - What triggers the workflow
  - What are the steps in the workflow
  - What are the decision points
  - What are the outcomes
- **Create Comprehensive Use Case List**: Enumerate ALL use cases identified from the analysis above

### Phase 3: Use Case Elaboration (Detail each use case)
For each use case identified:
- **Search for Implementation Evidence**:
  - **If fact-graph loaded**: Query fact-graph for implementation details
    ```python
    if fact_graph_loaded:
        # Find the endpoint for this use case
        use_case_endpoint = find_entity_by_name('CreateClaim')  # example

        if use_case_endpoint:
            endpoint_id = use_case_endpoint['id']

            # Get HTTP method
            http_method_facts = [f for f in facts
                                 if f['subject_id'] == endpoint_id
                                 and f['predicate'] == 'http_method']

            # Get parameters
            param_facts = [f for f in facts
                          if f['subject_id'] == endpoint_id
                          and f['predicate'] == 'accepts_param']

            # Get authorization requirements
            auth_facts = [f for f in facts
                         if f['subject_id'] == endpoint_id
                         and f['predicate'] in ['requires_auth', 'authorizes_via']]

            # Get controller->service call chain
            calls_relations = [r for r in relations
                              if r['source_id'] == endpoint_id
                              and r['type'] == 'calls']

            # Get service methods
            for call_rel in calls_relations:
                service = get_entity_by_id(call_rel['target_id'])

                # Get validation facts for this service
                validation_facts = [f for f in facts
                                   if f['subject_id'] == service['id']
                                   and f['predicate'] in ['validates', 'is_required', 'max_length']]

                # Get business rules
                business_rules = [f for f in facts
                                 if f['subject_id'] == service['id']
                                 and f['predicate'] == 'business_rule']

            # Get database entities involved
            reads_relations = [r for r in relations
                              if r['source_id'] == endpoint_id
                              and r['type'] == 'reads_from']
            writes_relations = [r for r in relations
                               if r['source_id'] == endpoint_id
                               and r['type'] == 'writes_to']

            # Use evidence fields for precise citations
            for fact in validation_facts:
                citation_file = fact['evidence'][0]['file']
                citation_lines = fact['evidence'][0]['line_range']
                # Use for inline citation: [📄](citation_file:citation_lines[0])
    else:
        # Fallback: Use Task/Explore to find implementation evidence
    ```
  - **If fact-graph NOT loaded**: Use Task/Explore to find:
    - Controller methods that implement the use case
    - Service/manager methods with business logic
    - Validation logic and business rules
    - Database models and entities involved
    - API endpoints that support the use case
- **Gather Citations**: Collect file paths and line numbers BEFORE writing (from fact evidence or code search)
- **Write Use Case WITH Citations**: Include:
  - Actor(s) involved with citations to authorization/permission checks
  - Goal statement
  - Preconditions with citations to validation logic
  - Main flow with citations to controller/service methods
  - Postconditions with citations to data changes/side effects
  - Alternative/exception flows with citations to error handling
  - Business rules referenced with citations to validation logic

### Phase 4: Document Generation with Inline Citations (Synthesis with Provenance)

**CRITICAL: Citations must be generated inline as you write, not added later.**

1. **Write use-case-by-use-case with immediate citation**:
   - Identify which use case to write
   - BEFORE writing the use case, search for ALL implementation evidence
   - Write the use case WITH citations inline from the start
   - Never write a step without immediately adding its citation

2. **Citation-First Writing Workflow**:
   ```
   For each use case:
   a) Identify the use case (e.g., "Administrator Creates New Claim")
   b) Search NOW for controller methods, validation, business logic
   c) Write preconditions WITH citations to validation/authorization
   d) Write each main flow step WITH citation to implementation
   e) Write postconditions WITH citations to data changes
   f) Write alternatives WITH citations to error handling
   g) Move to next use case
   ```

3. **Use Case Generation Process**:
   - **Plan**: List all use cases to document for the domain
   - **Search**: Use Task/Explore to find implementation for current use case
   - **Write**: Compose use case with inline citations for every step
   - **Validate**: Verify every step/condition has a citation before moving to next use case

4. **Citation Standards** (apply during writing):
   - Actor identification → cite authorization middleware or permission checks
   - Preconditions → cite validation methods, guards, or authorization logic
   - Main flow steps → cite controller methods, service methods, or business logic
   - Postconditions → cite database operations, event publications, or state changes
   - Alternative flows → cite error handling, exception logic, or validation failures
   - Business rules → cite validation methods, business logic, or rule engines

5. **Citation Format**:
   - Inline: `step description [📄](path/to/file.ext:line)`
   - Explicit: `step description [source](path/to/file.ext:line-range)`
   - Multiple sources: `step description [1](path1:line) [2](path2:line)`

6. **Quality Criteria** (verify as you write each use case):
   - Every actor has a citation to where they're authorized
   - Every precondition has a citation to where it's validated
   - Every main flow step has a citation to its implementation
   - Every postcondition has a citation to where data is changed
   - Every alternative flow has a citation to error/exception handling
   - Citations use specific line numbers, not vague references

**Example of Citation-First Writing:**

❌ **WRONG - Writing first, citing later:**
```
Use Case: Administrator Creates Claim
Main Flow:
1. Administrator accesses claim creation form
2. Administrator enters claim details
3. System validates claim
4. System creates claim
[Later: try to find and add citations]
```

✅ **CORRECT - Citing inline during initial writing:**
```
For use case "Administrator Creates Claim":
1. Search NOW: Find ClaimController.CreateClaim, validation, business logic
2. Gather evidence: ClaimController.cs:71-76, ClaimManager.cs:138-188, validation
3. Write WITH citations:

**Main Flow**:
1. Administrator accesses claim creation form [📄](../src/CTCM.API/CTCM.API.ClaimService/Controllers/ClaimController.cs:71-76)
2. Administrator enters required claim details [📄](../src/CTCM.API/CTCM.API.ClaimService/Dto/ClaimDetailsDto.cs:17-67)
3. System validates all required fields [📄](../src/CTCM.API/CTCM.API.ClaimService/Manager/ClaimManager.cs:140-145)
4. System creates claim record [📄](../src/CTCM.API/CTCM.API.ClaimService/Manager/ClaimManager.cs:147-149)
```

### Phase 5: Review & Polish (Quality assurance)
- Verify all use cases are comprehensive and cover the domain
- Ensure consistency across use cases
- Validate all citations point to actual implementations
- Check that all actors are properly identified
- Add any missing alternative flows
- Ensure NO use cases lack citations
- Validate use case numbering and organization

---

## Incremental Document Writing Process

**⚠️ MANDATORY: All use case documentation must be written incrementally to manage context efficiently and avoid token limits.**

### Why Incremental Writing?
- Long documents (30-40 min read) can exceed context windows if written all at once
- Reading the full file before each append wastes tokens
- Incremental writing allows indefinite document length
- More efficient and reliable for comprehensive documentation

### Initial Setup

1. **Create the initial document** with:
   - Front matter (title, audience, reading time, table of contents)
   - Requirements Overview or Introduction section
   - First 1-2 use cases or actor groups
   - Add marker at the end: `<!-- MORE CONTENT TO FOLLOW -->`

Example:
```markdown
# Use Cases: Pipeline Point Infrastructure Management
[front matter...]
## Actor 1: Pipeline Operations Data Steward
### UC-001: Create New Pipeline Point
[full use case with citations...]
<!-- MORE CONTENT TO FOLLOW -->
```

### For Each Additional Section

2. **Use the Edit tool** to replace the marker with new content:
   - **old_string**: `<!-- MORE CONTENT TO FOLLOW -->`
   - **new_string**: `[NEW USE CASE OR SECTION]\n\n<!-- MORE CONTENT TO FOLLOW -->`

3. **DO NOT read the full file** before appending - the Edit tool will find and replace the marker

4. **For each use case you write:**
   - Search for implementation evidence FIRST using Task/Explore or direct file reads
   - Gather all file paths and line numbers BEFORE writing prose
   - Write the use case WITH inline citations as you compose each step
   - Never write a precondition, main flow step, or postcondition without immediately adding its citation
   - Replace the marker and continue to the next use case

### Writing Pattern for Each Use Case

```
For each use case:
1. Search NOW: Find controller, service methods, validation logic
2. Gather citations: Collect file:line references
3. Write WITH citations:
   - Actor [📄](auth/check:line)
   - Preconditions [📄](validation:line)
   - Main Flow Step 1 [📄](controller:line)
   - Main Flow Step 2 [📄](service:line)
   - Postconditions [📄](data-change:line)
   - Alternatives [📄](error-handling:line)
4. Replace marker with: use case content + marker
5. Move to next use case
```

### Final Step

5. **Remove the marker** when writing the last section (Related Documents, Footer)
   - **old_string**: `<!-- MORE CONTENT TO FOLLOW -->`
   - **new_string**: `[FINAL SECTION CONTENT]\n\n---\n\n*Generated By LegacyLift AI by CapTech*`

### Key Rules

- ✅ Write use-case-by-use-case incrementally
- ✅ Replace the marker each time using Edit tool (don't read the whole file)
- ✅ Generate citations DURING writing (not after)
- ✅ Search for evidence BEFORE writing each use case
- ✅ Use Edit tool with exact marker text for find/replace
- ❌ DO NOT read the entire file between use cases
- ❌ DO NOT write use case steps first and add citations later
- ❌ DO NOT skip the marker (always add it until the final section)

### Example Workflow

```
1. Write: Front matter + UC-001 to UC-003 + marker
2. Edit: Replace marker with UC-004 to UC-006 + marker
3. Edit: Replace marker with UC-007 to UC-009 + marker
4. Edit: Replace marker with UC-010 to UC-012 + marker
5. Edit: Replace marker with Final sections + footer (no marker)
```

### Token Efficiency

This approach:
- Keeps context usage minimal (only marker location needed, not full file)
- Allows documents of any length to be created
- Maintains citation quality throughout
- Prevents context window exhaustion
- Enables you to write 50+ use cases without issues

---

## Key Features

### 🎯 **Comprehensive Coverage**
Systematically identifies ALL use cases for a domain:
- Primary success scenarios
- Alternative flows and exceptions
- Edge cases and error conditions
- Administrative and maintenance tasks
- Integration and external actor scenarios

### 👥 **Actor-Centered Organization**
Use cases organized by actor/role:
- Internal users (administrators, analysts, reviewers)
- External users (clients, partners, attorneys)
- System actors (scheduled jobs, integrations)
- Clear role identification and permissions

### 📋 **Structured Use Case Format**
Each use case includes:
- **Actor**: Who performs the use case
- **Goal**: What the actor wants to accomplish
- **Preconditions**: What must be true before execution (with citations)
- **Main Flow**: Step-by-step success path (with citations)
- **Postconditions**: What changes after execution (with citations)
- **Alternative Flows**: Error handling and exceptions (with citations)
- **Business Rules Referenced**: Links to relevant business rules (with citations)

### 🔗 **Deep Code Integration**
Every use case step includes source code references:
- File paths with line numbers
- Direct links to controller methods
- Validation and business logic citations
- Verifiable against actual codebase

### 📊 **Visual Representations**
Automatically generates Mermaid diagrams:
- Use case diagrams showing actors and use cases
- Sequence diagrams for complex workflows
- State diagrams for entity lifecycle use cases

### 🔄 **Traceability**
Clear traceability between:
- Use cases and functional requirements
- Use cases and API endpoints
- Use cases and business rules
- Use cases and implementation code

## What Gets Analyzed

The skill examines:

### Business Requirements Documents
- ✅ Functional requirements by domain
- ✅ Business rules and validation logic
- ✅ User workflows and processes
- ✅ Existing use cases and user stories
- ✅ Compliance and security requirements

### Source Code
- ✅ Controller methods and API endpoints
- ✅ Service/manager business logic
- ✅ Validation logic and rules
- ✅ Authorization and permission checks
- ✅ Database models and entities
- ✅ Error handling and exceptions
- ✅ Event publications and side effects

### Architecture
- ✅ Actor roles and permissions
- ✅ Integration points
- ✅ External system interactions
- ✅ Asynchronous workflows

## Output Quality Standards

Generated use case documentation includes:

✅ **Clear Structure** - Table of contents, actor groups, use case sections
✅ **Estimated Reading Time** - Help readers allocate time
✅ **Target Audience** - Who should read this document
✅ **Comprehensive Coverage** - ALL use cases for the domain identified
✅ **Actor Identification** - Clear identification of all actors and roles
✅ **Detailed Flows** - Step-by-step main and alternative flows
✅ **Exhaustive Citations** - **Every** step, precondition, postcondition, and alternative has inline source code citations with precise file paths and line numbers
✅ **Verifiable Claims** - All steps can be validated by following citation links to actual implementation code
✅ **Acceptance Criteria** - Testable acceptance criteria for each use case
✅ **Business Rules Cross-Reference** - Links to business rules documentation
✅ **Diagrams** - Visual use case diagrams and sequence diagrams
✅ **Traceability** - Clear mapping to functional requirements and implementation
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
    ├── 08-USE-CASES-CLAIMS.md  ← Generated by this skill
    └── 08-USE-CASES-ACCESS-CONTROL.md  ← Generated by this skill
```

## Technical Implementation

This skill uses Claude Code's advanced capabilities:

- **Task Tool**: Launches specialized exploration agents for thorough analysis
- **Parallel Analysis**: Analyzes multiple aspects concurrently
- **Code Search**: Grep and Glob for finding implementations
- **File Reading**: Deep inspection of requirements docs and source files
- **Template System**: Consistent use case documentation structure
- **Diagram Generation**: Automatic Mermaid diagram creation
- **Citation Validation**: Verify all citations point to actual code

## Success Criteria

Documentation is considered complete when:

✅ All use cases for the domain are identified and documented
✅ **Every use case step has inline source code citations with file paths and line numbers (generated during initial writing, not added later)**
✅ **Preconditions cite validation logic or authorization checks**
✅ **Main flow steps cite controller/service implementation methods**
✅ **Postconditions cite data changes, events, or side effects**
✅ **Alternative flows cite error handling or exception logic**
✅ **No use case was written without citations - they were integral to the writing process**
✅ All actors are clearly identified with role descriptions
✅ Acceptance criteria are testable and specific
✅ Diagrams accurately represent use cases and workflows
✅ Cross-references to requirements are valid
✅ Technical accuracy is verified against source code
✅ **Citations can withstand scrutiny - they point to actual implementations**
✅ **Document never required post-processing to add citations - they had them from the start**

## Skill Execution

**⚠️ MANDATORY WORKFLOW: When writing any use case, you MUST:**
1. Search for implementation evidence FIRST using Task/Explore
2. Gather all file paths and line numbers for the use case
3. Write use case WITH citations inline for every step
4. Never write a step without its citation

When this skill is invoked, I will:

1. **Clarify the Context**
   - Identify the domain (e.g., CLAIMS, Access Control, Benefits Management)
   - Locate the business requirements document for the domain
   - Confirm output directory and file naming convention
   - Ask if there are specific actors or areas of focus

2. **Create Todo List**
   - Phase 1: Input Discovery & Analysis
   - Phase 2: Use Case Identification
   - Phase 3: Use Case Elaboration
   - Phase 4: Document Generation (with inline citations as you write)
   - Phase 5: Review & Polish

3. **Execute Systematically**
   - Read business requirements documentation thoroughly
   - Use Task/Explore to find all implementation code for the domain
   - Identify all actors, functional requirements, and workflows
   - Create comprehensive list of use cases
   - **For Phase 4 - Generate document with inline citations**:
     * Break document into logical sections by actor or use case group
     * For each use case:
       - Search for implementation evidence BEFORE writing
       - Gather all file paths and line numbers
       - Write use case WITH citations inline from the start
       - Validate every step has a citation before moving to next use case
     * **Never write a use case step without immediately adding its citation**
     * **Pattern: Search → Gather → Write-with-Citations → Validate → Next Use Case**
   - Cross-validate against source code

4. **Deliver Complete Documentation**
   - 08-USE-CASES-{DOMAIN}.md in markdown format
   - Placed in `legacylift-docs/` directory (or specified location)
   - Following proven template structure
   - With Mermaid diagrams, exhaustive inline source citations
   - **Every use case step backed by verifiable source code references from initial writing**
   - **No use case written without citations - they're integral to the writing process**
   - Ready for immediate use by all stakeholders

   When using this skill, you can specify parameters:
   ```
   /legacylift-classic:use-case-generator domain=CLAIMS input_doc=path/to/business-requirements.md output_dir=repos/my_project/legacylift-docs
   ```
   - `domain`: Required - the domain name (e.g., CLAIMS, AccessControl)
   - `input_doc`: Optional - path to business requirements document to analyze
   - `output_dir`: Optional - output directory (defaults to `{analyzed_repo_path}/legacylift-docs/`)

5. **Provide Summary**
   - Number of use cases documented
   - Actors identified
   - Coverage analysis (what was documented, any gaps)
   - Recommendations for testing focus areas

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

This skill uses supporting files in the `templates/` directory to ensure consistent, high-quality documentation output.

### Template Structure

| Template File | Purpose | Usage |
|---------------|---------|-------|
| **[08-USE-CASES-TEMPLATE.md](./templates/08-USE-CASES-TEMPLATE.md)** | Structure for use case docs | Guides use case organization, format, and content |

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
| 08 | [USE-CASES-{DOMAIN}](./templates/08-USE-CASES-TEMPLATE.md) ⭐ | **use-case-generator** | Comprehensive use case documentation |
| 09 | CITATION-VALIDATION-REPORT | citation-validator | Citation correctness validation |
| 10 | GAP-ANALYSIS-REPORT | gap-analyzer | Documentation-code gap analysis |

⭐ = Generated by this skill

### How Templates Are Used

During skill execution, I (Claude) will:

1. **Reference Template**: Read the use case template
2. **Extract Structure**: Use the template's sections, headings, and organization
3. **Fill with Analysis**: Replace placeholders with actual use cases from domain analysis
4. **Maintain Consistency**: Ensure all use cases follow the same professional format
5. **Adapt as Needed**: Customize sections based on domain specifics

### Template Features

The template includes:

- **Instructional Comments**: HTML comments guiding what content to include
- **Placeholder Syntax**: `{PLACEHOLDER}` markers for domain-specific values
- **Section Organization**: Pre-structured table of contents and actor groups
- **Use Case Format**: Standardized format for each use case
- **Diagram Scaffolds**: Mermaid diagram templates
- **Citation Examples**: Examples of proper inline citations
- **Acceptance Criteria Format**: Structure for testable criteria
