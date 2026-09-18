# Use Cases: {DOMAIN_NAME}

<!--
⚠️ CRITICAL CITATION REQUIREMENTS ⚠️

EVERY use case step, precondition, postcondition, and alternative flow MUST have an inline citation.
Use cases are implemented in code - cite where they're executed.

WORKFLOW FOR WRITING THIS DOCUMENT:
1. Search for controller methods, service logic, validation BEFORE writing each use case
2. Gather all file paths and line numbers BEFORE writing prose
3. Write use case WITH citations inline - never describe a step without citing its implementation
4. Use format: "Step description [📄](path/to/controller:line)"
5. Validate every step has a citation before moving to next use case

WHAT NEEDS CITATIONS:
✅ Actor identification (cite authorization/permission middleware)
✅ Every precondition (cite validation method, guard, or authorization check)
✅ Every main flow step (cite controller method, service method, or business logic)
✅ Every postcondition (cite database operation, event publication, or state change)
✅ Every alternative flow (cite error handler, exception logic, or validation failure)
✅ Business rules referenced (cite validation logic or business rule implementation)

GOOD EXAMPLE:
**Main Flow**:
1. User accesses claim creation form [📄](src/Controllers/ClaimController.cs:71-76)
2. User enters claim details [📄](src/Dto/ClaimDetailsDto.cs:17-67)
3. System validates required fields [📄](src/Manager/ClaimManager.cs:140-145)
4. System creates claim record [📄](src/Manager/ClaimManager.cs:147-149)

BAD EXAMPLE:
**Main Flow**:
1. User accesses claim creation form
2. User enters claim details
3. System validates required fields
4. System creates claim record
↑ No citations - unacceptable

TEMPLATE INSTRUCTIONS:
- Replace {DOMAIN_NAME} with actual domain name (e.g., "Claims Management", "Access Control")
- Replace {PROJECT_NAME} with actual project name
- Search for implementation evidence BEFORE writing each use case
- Cite every step, precondition, postcondition with [📄](path/file:line)
- Document use cases based on actual implementation code
- NEVER describe a use case step without citing where it's implemented
- Do not confabulate - every claim must be verifiable from source code
- Organize use cases by actor/role for easy navigation
-->

## Who Should Read This

This document is intended for:
- **Product Managers**: Understand {DOMAIN_NAME} functional capabilities and user scenarios
- **Business Analysts**: Document and validate use cases and acceptance criteria
- **Software Engineers**: Understand user flows and implement features correctly
- **QA Engineers**: Create test cases and test scenarios based on use cases
- **UX Designers**: Design user interfaces and experiences for each use case
- **Business Stakeholders**: Understand system capabilities from user perspective

**Prerequisites**: Familiarity with {domain concepts}

**Reading Time**: 30-40 minutes

---

## Table of Contents

1. [Overview](#overview)
2. [Actors & Roles](#actors--roles)
3. [Use Case Diagram](#use-case-diagram)
4. [Use Cases by Actor](#use-cases-by-actor)
5. [Traceability Matrix](#traceability-matrix)
6. [Related Documents](#related-documents)

---

## Overview

### Purpose of This Document

This document provides comprehensive use case documentation for the **{DOMAIN_NAME}** domain within the {PROJECT_NAME} system. It describes:
1. **Who** can perform actions (Actors & Roles)
2. **What** actions can be performed (Use Cases)
3. **How** those actions are accomplished (Flows)
4. **Why** actions are performed (Goals)
5. **Where** actions are implemented (Code Citations)

### Domain Scope

The {DOMAIN_NAME} domain encompasses {brief description of domain scope} [📄](path/to/relevant/controller:line).

**Key Capabilities**:
- {Capability 1} [📄](path/file:line)
- {Capability 2} [📄](path/file:line)
- {Capability 3} [📄](path/file:line)
<!-- List 5-10 key capabilities -->

---

## Actors & Roles

### Actor Definitions

This section defines all actors who interact with the {DOMAIN_NAME} domain.

```mermaid
mindmap
  root(({DOMAIN_NAME}<br/>Actors))
    Internal Users
      {Role 1}
        {Permission/Goal}
        {Permission/Goal}
      {Role 2}
        {Permission/Goal}
        {Permission/Goal}
    External Users
      {External Role 1}
        {Permission/Goal}
      {External Role 2}
        {Permission/Goal}
    System Actors
      {System Actor 1}
      {System Actor 2}
```

#### Internal Users

| Actor | Description | Key Permissions | Source |
|-------|-------------|-----------------|--------|
| **{Role Name}** | {Description of role and responsibilities} | {Permission 1}, {Permission 2} | [📄](path/to/authorization:line) |
| **{Role Name}** | {Description of role and responsibilities} | {Permission 1}, {Permission 2} | [📄](path/to/authorization:line) |
<!-- Repeat for each internal user role -->

#### External Users

| Actor | Description | Access Method | Source |
|-------|-------------|---------------|--------|
| **{External Role}** | {Description of external user type} | {How they access system} | [📄](path/to/auth:line) |
| **{External Role}** | {Description of external user type} | {How they access system} | [📄](path/to/auth:line) |
<!-- Repeat for each external user type -->

#### System Actors

| Actor | Description | Trigger | Source |
|-------|-------------|---------|--------|
| **{System Actor}** | {Description of automated actor} | {What triggers it} | [📄](path/to/scheduler:line) |
| **{System Actor}** | {Description of automated actor} | {What triggers it} | [📄](path/to/integration:line) |
<!-- Repeat for each system actor -->

---

## Use Case Diagram

```mermaid
graph TB
    subgraph "Internal Actors"
        Actor1["{Role 1}"]
        Actor2["{Role 2}"]
        Actor3["{Role 3}"]
    end

    subgraph "External Actors"
        ExtActor1["{External Role 1}"]
        ExtActor2["{External Role 2}"]
    end

    subgraph "{DOMAIN_NAME} Use Cases"
        UC1["UC-001: {Use Case Name}"]
        UC2["UC-002: {Use Case Name}"]
        UC3["UC-003: {Use Case Name}"]
        UC4["UC-004: {Use Case Name}"]
        UC5["UC-005: {Use Case Name}"]
        UC6["UC-006: {Use Case Name}"]
        UC7["UC-007: {Use Case Name}"]
        UC8["UC-008: {Use Case Name}"]
        <!-- Add all use cases -->
    end

    Actor1 --> UC1
    Actor1 --> UC2
    Actor2 --> UC3
    Actor2 --> UC4
    Actor3 --> UC5
    ExtActor1 --> UC6
    ExtActor2 --> UC7
    System --> UC8

    UC1 -.includes.-> UC2
    UC3 -.extends.-> UC4
```

---

## Use Cases by Actor

<!-- Organize use cases by actor/role for easy navigation -->

### {Role 1} Use Cases

#### UC-{XXX}: {Use Case Name}

**Actor**: {Primary Actor} [📄](path/to/authorization:line)

**Goal**: {What the actor wants to accomplish}

**Trigger**: {What initiates this use case} [📄](path/to/trigger:line)

**Frequency**: {How often this use case occurs}

**Priority**: {High/Medium/Low}

**Preconditions**:
- {Precondition 1} [📄](path/to/validation:line)
- {Precondition 2} [📄](path/to/guard:line)
- {Precondition 3} [📄](path/to/authorization:line)
<!-- List all conditions that must be true before execution -->

**Main Flow**:

```mermaid
sequenceDiagram
    participant Actor as {Actor}
    participant UI as User Interface
    participant Controller as {Controller}
    participant Service as {Service}
    participant DB as Database

    Actor->>UI: {Action} [📄](path:line)
    UI->>Controller: {Request} [📄](path:line)
    Controller->>Controller: Validate [📄](path:line)
    Controller->>Service: {Process} [📄](path:line)
    Service->>DB: {Data Operation} [📄](path:line)
    DB-->>Service: {Result} [📄](path:line)
    Service-->>Controller: {Response} [📄](path:line)
    Controller-->>UI: {Result} [📄](path:line)
    UI-->>Actor: {Confirmation} [📄](path:line)
```

1. {Actor} {action description} [📄](path/to/controller:line)
2. System {validation/processing step} [📄](path/to/validation:line)
3. System {business logic step} [📄](path/to/service:line)
4. System {data operation step} [📄](path/to/repository:line)
5. System {event/notification step} [📄](path/to/event:line)
6. System {response step} [📄](path/to/controller:line)
<!-- Document each step in the success path -->

**Postconditions**:
- {Outcome 1} [📄](path/to/data-change:line)
- {Outcome 2} [📄](path/to/event-publication:line)
- {Outcome 3} [📄](path/to/state-change:line)
<!-- List all outcomes and state changes after successful execution -->

**Alternative Flows**:

**Alt-1: {Exception/Alternative Scenario}**
- **Condition**: {When this alternative occurs} [📄](path/to/condition:line)
- **Steps**:
  1. {Step} [📄](path/to/error-handler:line)
  2. {Step} [📄](path/to/alternative-logic:line)
- **Outcome**: {What happens} [📄](path/to/outcome:line)

**Alt-2: {Exception/Alternative Scenario}**
- **Condition**: {When this alternative occurs} [📄](path/to/validation-failure:line)
- **Steps**:
  1. {Step} [📄](path/to/error-response:line)
  2. {Step} [📄](path/to/logging:line)
- **Outcome**: {What happens} [📄](path/to/outcome:line)

<!-- Repeat for each alternative flow -->

**Business Rules Referenced**:
- **BR-{DOMAIN}-{XXX}**: {Business rule description} [📄](path/to/business-rule:line)
- **BR-{DOMAIN}-{XXX}**: {Business rule description} [📄](path/to/validation:line)
<!-- Reference business rules that apply to this use case -->

**Acceptance Criteria**:
- [ ] {Testable criterion 1} [📄](path/to/implementation:line)
- [ ] {Testable criterion 2} [📄](path/to/validation:line)
- [ ] {Testable criterion 3} [📄](path/to/outcome:line)
- [ ] {Testable criterion 4} [📄](path/to/error-handling:line)
- [ ] {Testable criterion 5} [📄](path/to/authorization:line)
<!-- List specific, testable acceptance criteria -->

**Related Requirements**:
- **FR-{DOMAIN}-{XXX}**: {Functional requirement} - See [Business Rules & Requirements](03-BUSINESS-RULES-AND-REQUIREMENTS-{Domain}.md#fr-{domain}-{xxx})

**Related Use Cases**:
- **UC-{XXX}**: {Related use case} - {Relationship description}

---

<!-- Repeat the above use case structure for ALL use cases in the domain -->
<!-- Organize by actor/role groups for easy navigation -->

### {Role 2} Use Cases

#### UC-{XXX}: {Use Case Name}
<!-- Same structure as above -->

---

### {External Role} Use Cases

#### UC-{XXX}: {Use Case Name}
<!-- Same structure as above -->

---

### System Actor Use Cases

#### UC-{XXX}: {Use Case Name}

**Actor**: System (Automated Process) [📄](path/to/scheduler:line)

**Goal**: {What the automated process accomplishes}

**Trigger**: {What initiates this process (schedule, event, etc.)} [📄](path/to/trigger:line)

**Frequency**: {How often this executes}

<!-- Follow same structure as user-initiated use cases -->

---

## Traceability Matrix

This matrix provides traceability between use cases, functional requirements, API endpoints, and implementation.

| Use Case ID | Use Case Name | Actors | Functional Requirements | API Endpoints | Implementation |
|-------------|---------------|--------|------------------------|---------------|----------------|
| **UC-{XXX}** | {Use Case Name} | {Actor} | FR-{DOMAIN}-{XXX} | `{HTTP_METHOD} /api/{endpoint}` | [📄](path/to/controller:line) |
| **UC-{XXX}** | {Use Case Name} | {Actor} | FR-{DOMAIN}-{XXX} | `{HTTP_METHOD} /api/{endpoint}` | [📄](path/to/controller:line) |
| **UC-{XXX}** | {Use Case Name} | {Actor} | FR-{DOMAIN}-{XXX}, FR-{DOMAIN}-{XXX} | `{HTTP_METHOD} /api/{endpoint}` | [📄](path/to/controller:line) |
<!-- Repeat for all use cases -->

---

## Use Case Summary Statistics

### Coverage Analysis

```mermaid
pie title "Use Cases by Actor Type"
    "Internal Users" : {count}
    "External Users" : {count}
    "System Actors" : {count}
```

```mermaid
pie title "Use Cases by Priority"
    "High" : {count}
    "Medium" : {count}
    "Low" : {count}
```

### Use Case Counts

| Actor/Role | Number of Use Cases | Primary Use Cases |
|------------|---------------------|-------------------|
| **{Role 1}** | {count} | {List primary use case IDs} |
| **{Role 2}** | {count} | {List primary use case IDs} |
| **{External Role}** | {count} | {List primary use case IDs} |
| **System** | {count} | {List primary use case IDs} |
| **Total** | **{total}** | |

---

## Testing Considerations

### Priority Testing Areas

Based on use case analysis, focus testing efforts on:

1. **Critical Path Use Cases** (High Priority):
   - UC-{XXX}: {Use Case Name} - {Why it's critical}
   - UC-{XXX}: {Use Case Name} - {Why it's critical}

2. **Complex Use Cases** (Many alternative flows):
   - UC-{XXX}: {Use Case Name} - {Number of alternatives} alternative flows
   - UC-{XXX}: {Use Case Name} - {Number of alternatives} alternative flows

3. **Integration Use Cases** (External dependencies):
   - UC-{XXX}: {Use Case Name} - Integrates with {External System}
   - UC-{XXX}: {Use Case Name} - Integrates with {External System}

### Test Scenario Recommendations

For comprehensive test coverage, create test scenarios covering:
- ✅ All main flows for high-priority use cases
- ✅ All alternative flows documented
- ✅ All business rules referenced in use cases
- ✅ All actor permission/authorization checks
- ✅ All precondition validations
- ✅ All postcondition verifications
- ✅ Edge cases and boundary conditions
- ✅ Error handling and exception scenarios

---

## Related Documents

- [Executive Summary](00-EXECUTIVE-SUMMARY.md)
- [System Architecture](01-SYSTEM-ARCHITECTURE.md)
- [Data Model & Relationships](02-DATA-MODEL-AND-RELATIONSHIPS.md)
- [Business Rules & Requirements](03-BUSINESS-RULES-AND-REQUIREMENTS.md)
- [Business Rules & Requirements - {Domain}](03-BUSINESS-RULES-AND-REQUIREMENTS-{Domain}.md)
- [Integration & API Guide](04-INTEGRATION-AND-API-GUIDE.md)

---

*Generated By LegacyLift AI by CapTech*
*Generated on: {GENERATED_DATETIME}*
