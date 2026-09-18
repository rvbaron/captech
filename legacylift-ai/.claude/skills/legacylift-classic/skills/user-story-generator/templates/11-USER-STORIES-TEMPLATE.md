# User Stories: {DOMAIN_NAME}

<!--
⚠️ CRITICAL CITATION REQUIREMENTS ⚠️

EVERY user story must have inline citations for:
- Acceptance criteria (cite validation, authorization, business logic)
- Technical implementation (cite controller, service methods)
- Business rules (cite validation methods, business rule implementation)

User stories describe WHAT to build - cite WHERE it's already implemented (or where it should be).

WORKFLOW FOR WRITING THIS DOCUMENT:
1. Search for implementation evidence BEFORE writing each user story
2. Gather all file paths and line numbers BEFORE writing prose
3. Write user story WITH citations inline - never describe acceptance criteria without citing implementation
4. Use format: "Acceptance criterion [📄](path/to/implementation:line)"
5. Validate every criterion has a citation before moving to next story

WHAT NEEDS CITATIONS:
✅ Acceptance criteria (cite validation, authorization, business logic where implemented)
✅ Technical implementation (cite controller methods, service methods, validators)
✅ Business rules (cite validation logic or business rule implementation)
✅ Related stories (use US-XXX format for cross-references)

GOOD EXAMPLE:
**Acceptance Criteria**:
- User can access claim creation form [📄](src/Controllers/ClaimController.cs:71-76)
- All required fields must be provided [📄](src/Dto/ClaimDetailsDto.cs:17-25)
- System validates claim amount is positive [📄](src/Validators/ClaimValidator.cs:140-145)
- Claim is saved to database [📄](src/Manager/ClaimManager.cs:147-149)

BAD EXAMPLE:
**Acceptance Criteria**:
- User can access claim creation form
- All required fields must be provided
- System validates claim amount is positive
- Claim is saved to database
↑ No citations - unacceptable

TEMPLATE INSTRUCTIONS:
- Replace {DOMAIN_NAME} with actual domain name (e.g., "Claims Management", "Access Control")
- Replace {PROJECT_NAME} with actual project name
- Search for implementation evidence BEFORE writing each user story
- Cite every acceptance criterion, technical implementation detail with [📄](path/file:line)
- Document user stories based on actual use cases and implementation code
- NEVER describe acceptance criteria without citing where it's validated/implemented
- Do not confabulate - every claim must be verifiable from source code
- Organize stories by epic for product backlog management
- Use INVEST principles: Independent, Negotiable, Valuable, Estimable, Small, Testable
-->

## Who Should Read This

This document is intended for:
- **Product Managers**: Prioritize and plan development iterations
- **Scrum Masters/Project Managers**: Plan sprints and track progress
- **Business Analysts**: Validate requirements and acceptance criteria
- **Software Engineers**: Understand user needs and implement features
- **QA Engineers**: Create test cases based on acceptance criteria
- **Business Stakeholders**: Understand development scope and priorities

**Prerequisites**: Familiarity with {domain concepts}, Agile/Scrum methodology

**Reading Time**: 45-60 minutes

---

## Table of Contents

1. [Overview](#overview)
2. [Epic Overview](#epic-overview)
3. [User Stories by Epic](#user-stories-by-epic)
4. [Traceability Matrix](#traceability-matrix)
5. [Backlog Statistics](#backlog-statistics)
6. [Related Documents](#related-documents)

---

## Overview

### Purpose of This Document

This document provides comprehensive user stories for the **{DOMAIN_NAME}** domain within the {PROJECT_NAME} system. It describes:
1. **Epics**: Major capabilities grouped by theme or entity lifecycle
2. **User Stories**: Specific features told from user perspective
3. **Acceptance Criteria**: Testable conditions for story completion
4. **Technical Implementation**: Where/how each story is implemented
5. **Dependencies**: Relationships between stories

### Domain Scope

The {DOMAIN_NAME} domain encompasses {brief description of domain scope} [📄](path/to/relevant/controller:line).

This user story backlog covers {estimated number} stories organized into {number} epics, representing a comprehensive rebuild/modernization of all {DOMAIN_NAME} capabilities.

### Story Format

All user stories follow the standard format:
```
As a [persona/role],
I want [functionality],
So that [business value/goal].
```

Each story includes:
- **Acceptance Criteria**: Testable conditions with citations
- **Technical Implementation**: Controller/service methods with citations
- **Business Rules**: Referenced business rules with citations
- **Related Stories**: Dependencies and relationships (US-XXX format)
- **Priority**: High/Medium/Low
- **Size**: Story point estimate (1, 2, 3, 5, 8, 13)

---

## Epic Overview

This section provides a high-level overview of all epics in the {DOMAIN_NAME} domain.

### Epic Definitions

```mermaid
mindmap
  root(({DOMAIN_NAME}<br/>Epics))
    Epic 1: {Epic Name}
      {Key Capability}
      {Key Capability}
      {Number} Stories
    Epic 2: {Epic Name}
      {Key Capability}
      {Key Capability}
      {Number} Stories
    Epic 3: {Epic Name}
      {Key Capability}
      {Key Capability}
      {Number} Stories
    Epic 4: {Epic Name}
      {Key Capability}
      {Key Capability}
      {Number} Stories
    Epic 5: {Epic Name}
      {Key Capability}
      {Key Capability}
      {Number} Stories
```

### Epic Summary

| Epic ID | Epic Name | Description | Story Count | Priority | Related Use Cases |
|---------|-----------|-------------|-------------|----------|-------------------|
| **EP-{XXX}** | {Epic Name} | {Brief description of epic scope and goals} | {count} | High/Med/Low | UC-{XXX}, UC-{YYY} |
| **EP-{XXX}** | {Epic Name} | {Brief description of epic scope and goals} | {count} | High/Med/Low | UC-{XXX}, UC-{YYY} |
| **EP-{XXX}** | {Epic Name} | {Brief description of epic scope and goals} | {count} | High/Med/Low | UC-{XXX}, UC-{YYY} |
| **EP-{XXX}** | {Epic Name} | {Brief description of epic scope and goals} | {count} | High/Med/Low | UC-{XXX}, UC-{YYY} |
| **EP-{XXX}** | {Epic Name} | {Brief description of epic scope and goals} | {count} | High/Med/Low | UC-{XXX}, UC-{YYY} |
<!-- Repeat for each epic (typically 5-8 epics per domain) -->

---

## User Stories by Epic

<!-- Organize user stories by epic for backlog management -->

### Epic 1: {Epic Name} (EP-{XXX})

**Epic Goal**: {What this epic accomplishes}

**Epic Scope**: {Description of capabilities covered by this epic}

**Related Use Cases**: UC-{XXX}, UC-{YYY}, UC-{ZZZ} - See [Use Cases: {Domain}](08-USE-CASES-{Domain}.md)

**Story Count**: {count} stories

---

#### US-{XXX}: {Story Title} [📄](path/to/implementation:line)

**Story**: As a **{persona/role}**, I want **{functionality}**, so that **{business value}**.

**Acceptance Criteria**:
- {Criterion 1} [📄](path/to/validation:line)
- {Criterion 2} [📄](path/to/authorization:line)
- {Criterion 3} [📄](path/to/business-logic:line)
- {Criterion 4} [📄](path/to/data-operation:line)
- {Criterion 5} [📄](path/to/error-handling:line)
<!-- List 3-7 specific, testable acceptance criteria -->

**Technical Implementation**:
- **Controller**: {ControllerName}.{MethodName}() [📄](path/to/controller:line)
- **Service**: {ServiceName}.{MethodName}() [📄](path/to/service:line)
- **Validation**: {ValidatorName}.{MethodName}() [📄](path/to/validator:line)
- **Data Access**: {RepositoryName}.{MethodName}() [📄](path/to/repository:line)
<!-- Cite key implementation components -->

**Business Rules**:
- **BR-{DOMAIN}-{XXX}**: {Business rule description} [📄](path/to/business-rule:line)
- **BR-{DOMAIN}-{XXX}**: {Business rule description} [📄](path/to/validation:line)
<!-- Reference applicable business rules -->

**Related Stories**:
- **Depends On**: US-{XXX} (must be completed first)
- **Related**: US-{YYY}, US-{ZZZ}
- **Blocks**: US-{AAA} (this story blocks another)

**Priority**: High | **Size**: Medium (5 story points)

**Notes**: {Any additional context, technical considerations, or open questions}

---

#### US-{XXX}: {Story Title} [📄](path/to/implementation:line)

<!-- Repeat user story structure for all stories in this epic -->
<!-- Typically 10-30 stories per epic -->

---

### Epic 2: {Epic Name} (EP-{XXX})

**Epic Goal**: {What this epic accomplishes}

**Epic Scope**: {Description of capabilities covered by this epic}

**Related Use Cases**: UC-{XXX}, UC-{YYY} - See [Use Cases: {Domain}](08-USE-CASES-{Domain}.md)

**Story Count**: {count} stories

---

#### US-{XXX}: {Story Title} [📄](path/to/implementation:line)

<!-- Same structure as Epic 1 stories -->

---

<!-- Repeat epic structure for all epics (typically 5-8 epics) -->

### Epic 3: {Epic Name} (EP-{XXX})

<!-- Same structure -->

---

### Epic 4: {Epic Name} (EP-{XXX})

<!-- Same structure -->

---

### Epic 5: {Epic Name} (EP-{XXX})

<!-- Same structure -->

---

## Traceability Matrix

This matrix provides traceability between user stories, use cases, functional requirements, and implementation.

| Story ID | Story Title | Epic | Use Cases | Functional Requirements | Implementation | Priority |
|----------|-------------|------|-----------|------------------------|----------------|----------|
| **US-{XXX}** | {Story Title} | EP-{XXX} | UC-{XXX} | FR-{DOMAIN}-{XXX} | [📄](path/to/controller:line) | High |
| **US-{XXX}** | {Story Title} | EP-{XXX} | UC-{XXX} | FR-{DOMAIN}-{XXX} | [📄](path/to/controller:line) | High |
| **US-{XXX}** | {Story Title} | EP-{XXX} | UC-{XXX}, UC-{YYY} | FR-{DOMAIN}-{XXX} | [📄](path/to/service:line) | Med |
| **US-{XXX}** | {Story Title} | EP-{XXX} | UC-{YYY} | FR-{DOMAIN}-{XXX}, FR-{DOMAIN}-{YYY} | [📄](path/to/controller:line) | Med |
<!-- Repeat for all user stories -->

---

## Backlog Statistics

### Story Distribution

```mermaid
pie title "User Stories by Epic"
    "{Epic 1 Name}" : {count}
    "{Epic 2 Name}" : {count}
    "{Epic 3 Name}" : {count}
    "{Epic 4 Name}" : {count}
    "{Epic 5 Name}" : {count}
```

```mermaid
pie title "User Stories by Priority"
    "High" : {count}
    "Medium" : {count}
    "Low" : {count}
```

```mermaid
pie title "User Stories by Size"
    "Small (1-2 pts)" : {count}
    "Medium (3-5 pts)" : {count}
    "Large (8-13 pts)" : {count}
```

### Epic Story Counts

| Epic ID | Epic Name | Story Count | Total Story Points | Avg Story Size | Priority Breakdown |
|---------|-----------|-------------|-------------------|----------------|-------------------|
| **EP-{XXX}** | {Epic Name} | {count} | {points} | {avg} pts | High: {count}, Med: {count}, Low: {count} |
| **EP-{XXX}** | {Epic Name} | {count} | {points} | {avg} pts | High: {count}, Med: {count}, Low: {count} |
| **EP-{XXX}** | {Epic Name} | {count} | {points} | {avg} pts | High: {count}, Med: {count}, Low: {count} |
| **Total** | | **{total stories}** | **{total points}** | **{avg}** pts | High: {count}, Med: {count}, Low: {count} |

### Story Dependencies

```mermaid
graph LR
    US{XXX}["US-{XXX}: {Story}"]
    US{YYY}["US-{YYY}: {Story}"]
    US{ZZZ}["US-{ZZZ}: {Story}"]
    US{AAA}["US-{AAA}: {Story}"]
    US{BBB}["US-{BBB}: {Story}"]

    US{XXX} --> US{YYY}
    US{XXX} --> US{ZZZ}
    US{YYY} --> US{AAA}
    US{ZZZ} --> US{AAA}
    US{AAA} --> US{BBB}

    classDef highPriority fill:#ff6b6b,stroke:#c92a2a
    classDef medPriority fill:#ffd93d,stroke:#f08c00
    classDef lowPriority fill:#95e1d3,stroke:#38ada9

    class US{XXX},US{YYY} highPriority
    class US{ZZZ},US{AAA} medPriority
    class US{BBB} lowPriority
```

---

## Sprint Planning Guidance

### Recommended Sprint Groupings

Based on dependencies and priorities, consider grouping stories into sprints:

**Sprint 1 (Recommended)**: Foundation Stories
- US-{XXX}: {Story} (High, 5 pts)
- US-{XXX}: {Story} (High, 3 pts)
- US-{XXX}: {Story} (High, 5 pts)
- **Total**: 13 story points

**Sprint 2 (Recommended)**: Core Features
- US-{XXX}: {Story} (High, 8 pts)
- US-{XXX}: {Story} (Med, 5 pts)
- **Total**: 13 story points

<!-- Suggest 4-6 sprint groupings based on dependencies and team velocity -->

### Critical Path Stories

These stories are on the critical path and should be prioritized:
1. US-{XXX}: {Story} - Blocks {count} other stories
2. US-{XXX}: {Story} - Blocks {count} other stories
3. US-{XXX}: {Story} - Blocks {count} other stories

### High-Risk Stories

These stories have higher complexity or uncertainty:
- US-{XXX}: {Story} - {Risk description}
- US-{XXX}: {Story} - {Risk description}
- **Recommendation**: Plan spike stories or proof-of-concepts for these

---

## Persona Reference

### Primary Personas

| Persona | Description | Key Goals | Related Stories |
|---------|-------------|-----------|-----------------|
| **{Persona 1}** | {Description of role and responsibilities} | {Goal 1}, {Goal 2} | US-{XXX}, US-{YYY}, ... |
| **{Persona 2}** | {Description of role and responsibilities} | {Goal 1}, {Goal 2} | US-{XXX}, US-{YYY}, ... |
| **{Persona 3}** | {Description of role and responsibilities} | {Goal 1}, {Goal 2} | US-{XXX}, US-{YYY}, ... |
<!-- List all personas referenced in user stories -->

---

## Definition of Done

For each user story to be considered complete:

- [ ] All acceptance criteria are met and verified
- [ ] Code is implemented according to technical implementation plan
- [ ] Unit tests written and passing (>80% code coverage)
- [ ] Integration tests written and passing
- [ ] Code reviewed and approved by at least one team member
- [ ] Business rules validation is implemented and tested
- [ ] Error handling is implemented for all failure scenarios
- [ ] Security requirements are met (authorization, validation, etc.)
- [ ] API documentation is updated (if applicable)
- [ ] User documentation is updated (if applicable)
- [ ] Story is tested in staging environment
- [ ] Product owner has accepted the story

---

## Related Documents

- [Executive Summary](00-EXECUTIVE-SUMMARY.md)
- [System Architecture](01-SYSTEM-ARCHITECTURE.md)
- [Data Model & Relationships](02-DATA-MODEL-AND-RELATIONSHIPS.md)
- [Business Rules & Requirements](03-BUSINESS-RULES-AND-REQUIREMENTS.md)
- [Business Rules & Requirements - {Domain}](03-BUSINESS-RULES-AND-REQUIREMENTS-{Domain}.md)
- [Integration & API Guide](04-INTEGRATION-AND-API-GUIDE.md)
- [Use Cases - {Domain}](08-USE-CASES-{Domain}.md)

---

*Generated By LegacyLift AI by CapTech*
*Generated on: {GENERATED_DATE}*