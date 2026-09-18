<!--
This is a template for the Table Validation Executive Summary document.
Replace all {PLACEHOLDER} markers with actual project-specific values.
Follow the structure provided to ensure comprehensive coverage.
This document is suitable for all stakeholders: executives, architects, DBAs, and engineers.
-->

<!-- PAGINATION: This document may need to be generated in parts (150-250 lines each) if content is large. -->

# Table Validation Executive Summary
## SQL DDL vs {ORM_FRAMEWORK} ORM Mapping Analysis

**Date:** {GENERATION_DATE}
**System:** {SYSTEM_NAME}
**Tables Analyzed:** {TOTAL_SQL_TABLES} SQL tables vs {TOTAL_ORM_MAPPINGS} {ORM_FRAMEWORK} mappings

---

## Overall Assessment: {GRADE}

<!-- Grade options: ✅ EXCELLENT, ✅ GOOD, ⚠️ FAIR, ❌ NEEDS IMPROVEMENT -->

{HIGH_LEVEL_ASSESSMENT_PARAGRAPH}

### Summary Statistics:
- **Total SQL Tables:** {TOTAL_SQL_TABLES}
- **{ORM_FRAMEWORK} Mappings:** {TOTAL_ORM_MAPPINGS} (including subdirectories)
- **Core Entities Fully Mapped:** {CORE_ENTITIES_MAPPED}/{TOTAL_CORE_ENTITIES} ({CORE_ENTITIES_PERCENTAGE}%)
- **Perfect Matches:** {PERFECT_MATCH_DESCRIPTION}
- **Tables Without Mappings:** {UNMAPPED_TABLES_COUNT} ({UNMAPPED_REASON})

---

## Core Entities Validation Results

### {VALIDATION_STATUS} ALL CORE ENTITIES: {OVERALL_STATUS}

<!-- Create a table for each core entity with validation status -->

| Entity | Columns | FK Relationships | {ORM_FRAMEWORK} Status |
|--------|---------|------------------|----------------------|
| **{ENTITY_1_NAME}** | {ENTITY_1_COLUMNS} | {ENTITY_1_RELATIONSHIPS} | {ENTITY_1_STATUS} |
| **{ENTITY_2_NAME}** | {ENTITY_2_COLUMNS} | {ENTITY_2_RELATIONSHIPS} | {ENTITY_2_STATUS} |
<!-- Repeat for all core entities -->

<!--
INSTRUCTIONS:
- List ALL core entities (typically 8-15 entities)
- Show column count, relationship count, and mapping status
- Use ✅ Complete, ⚠️ Partial, ❌ Missing for status
-->

---

## Key Findings

### 1. Column Coverage {STATUS_ICON}
<!-- Document whether all columns in SQL tables are mapped in ORM -->
- **{COLUMN_COVERAGE_DESCRIPTION}**
- {AUDIT_FIELDS_DESCRIPTION}
- {TIMESTAMP_LOCKING_DESCRIPTION}

### 2. Relationship Integrity {STATUS_ICON}
<!-- Document whether all foreign keys are represented as ORM associations -->
- **{RELATIONSHIP_COVERAGE_DESCRIPTION}**
- **{BIDIRECTIONAL_RELATIONSHIPS_DESCRIPTION}**
- **{CASCADE_RULES_DESCRIPTION}**

### 3. Constraint Validation {STATUS_ICON}
<!-- Document constraint handling (PK, FK, NOT NULL, unique) -->
- **Primary keys:** {PRIMARY_KEY_DESCRIPTION}
- **Foreign keys:** {FOREIGN_KEY_DESCRIPTION}
- **NOT NULL:** {NOT_NULL_DESCRIPTION}
- **Unique constraints:** {UNIQUE_CONSTRAINT_DESCRIPTION}

### 4. Custom Type Mappings {STATUS_ICON}
<!-- Document custom type converters and UserTypes -->
Sophisticated type handling:
- `{CUSTOM_TYPE_1_NAME}` - {CUSTOM_TYPE_1_DESCRIPTION}
- `{CUSTOM_TYPE_2_NAME}` - {CUSTOM_TYPE_2_DESCRIPTION}
- `{CUSTOM_TYPE_3_NAME}` - {CUSTOM_TYPE_3_DESCRIPTION}
<!-- Add more custom types as needed -->

<!--
CITATION REQUIREMENT:
- Cite SQL DDL files for table/column definitions [📄](path/to/table.sql:line)
- Cite ORM mapping files for entity mappings [📄](path/to/Entity.hbm.xml:line)
- Cite custom type implementations [📄](path/to/CustomType.cs:line)
-->

---

## Tables Without {ORM_FRAMEWORK} Mappings ({UNMAPPED_COUNT})

These are **intentional** and expected:

### By Category:
| Category | Count | Examples | Reason |
|----------|-------|----------|--------|
| **{CATEGORY_1_NAME}** | {CATEGORY_1_COUNT} | {CATEGORY_1_EXAMPLES} | {CATEGORY_1_REASON} |
| **{CATEGORY_2_NAME}** | {CATEGORY_2_COUNT} | {CATEGORY_2_EXAMPLES} | {CATEGORY_2_REASON} |
<!-- Common categories: Quartz Scheduler, External Integration, Temporary/Working, Specialized/Utility -->

**Assessment:** {UNMAPPED_TABLES_ASSESSMENT}

<!--
INSTRUCTIONS:
- Categorize all unmapped tables (Quartz, integration, temporary, specialized)
- Explain why each category is intentionally unmapped
- Provide examples for each category
-->

---

## Architecture Patterns Observed

### 1. Audit Trail Pattern {STATUS_ICON}
<!-- Document audit trail implementation -->
Every entity includes:
```
{AUDIT_TRAIL_EXAMPLE}
```

### 2. Temporal Data Pattern {STATUS_ICON}
<!-- Document temporal/historical data patterns -->
Status history tables use:
```
{TEMPORAL_DATA_EXAMPLE}
```
{TEMPORAL_DATA_DESCRIPTION}

### 3. Legacy Migration Support {STATUS_ICON}
<!-- Document legacy system integration patterns -->
Multiple "Old" columns for backward compatibility:
```
{LEGACY_COLUMNS_EXAMPLE}
```
{LEGACY_DESCRIPTION}

### 4. Optimistic Locking {STATUS_ICON}
<!-- Document concurrency control mechanisms -->
All core entities use timestamp-based optimistic locking:
```
{OPTIMISTIC_LOCKING_EXAMPLE}
```
{OPTIMISTIC_LOCKING_DESCRIPTION}

### 5. Type Table Organization {STATUS_ICON}
<!-- Document lookup/type table organization -->
Lookup/type tables organized in subdirectories:
- `{TYPE_TABLE_DIRECTORY_1}` - {TYPE_TABLE_DESCRIPTION_1}
- `{TYPE_TABLE_DIRECTORY_2}` - {TYPE_TABLE_DESCRIPTION_2}
{TYPE_TABLE_COVERAGE_DESCRIPTION}

<!-- Add more patterns as discovered in the codebase -->

---

## Significant Observations

### Strengths 💪

1. **{STRENGTH_1_TITLE}:** {STRENGTH_1_DESCRIPTION}
2. **{STRENGTH_2_TITLE}:** {STRENGTH_2_DESCRIPTION}
3. **{STRENGTH_3_TITLE}:** {STRENGTH_3_DESCRIPTION}
4. **{STRENGTH_4_TITLE}:** {STRENGTH_4_DESCRIPTION}
5. **{STRENGTH_5_TITLE}:** {STRENGTH_5_DESCRIPTION}
6. **{STRENGTH_6_TITLE}:** {STRENGTH_6_DESCRIPTION}
7. **{STRENGTH_7_TITLE}:** {STRENGTH_7_DESCRIPTION}

<!--
INSTRUCTIONS:
- Highlight 5-10 key strengths of the data model
- Common strengths: complete coverage, consistent patterns, bidirectional relationships, type safety, concurrency control, legacy support, clear organization
-->

### Smart Design Decisions 🎯

1. **{SMART_DECISION_1_TITLE}:** {SMART_DECISION_1_DESCRIPTION}
2. **{SMART_DECISION_2_TITLE}:** {SMART_DECISION_2_DESCRIPTION}
3. **{SMART_DECISION_3_TITLE}:** {SMART_DECISION_3_DESCRIPTION}

<!--
INSTRUCTIONS:
- Document clever solutions to common ORM challenges
- Common smart decisions: circular dependency handling, view mappings, lazy loading strategies, fetch strategies
-->

---

## Data Model Discrepancies

### Type Mismatches (Not Issues) ℹ️

Some mappings use custom types for business logic:

| SQL Type | {ORM_FRAMEWORK} Type | Reason |
|----------|---------------------|--------|
| {SQL_TYPE_1} | {ORM_TYPE_1} | {TYPE_REASON_1} |
| {SQL_TYPE_2} | {ORM_TYPE_2} | {TYPE_REASON_2} |
<!-- Add more type mappings as needed -->

**Assessment:** {TYPE_MISMATCH_ASSESSMENT}

### Property Name Differences ℹ️

Some properties renamed for clarity:

| SQL Column | {ORM_FRAMEWORK} Property | Reason |
|------------|-------------------------|--------|
| {SQL_COLUMN_1} | {ORM_PROPERTY_1} | {RENAME_REASON_1} |
| {SQL_COLUMN_2} | {ORM_PROPERTY_2} | {RENAME_REASON_2} |

**Assessment:** {PROPERTY_NAME_ASSESSMENT}

---

<!--
NOTE: The following sections are REMOVED per user requirements:
- Migration Readiness Assessment
- Recommendations

These will be addressed in later phases of the project.
-->

---

## Detailed Comparison Examples

### Example 1: {EXAMPLE_ENTITY_1} (Complex Relationships)

**SQL Foreign Keys:**
```sql
{SQL_FOREIGN_KEYS_EXAMPLE}
```

**{ORM_FRAMEWORK} Mappings:**
```xml
{ORM_MAPPINGS_EXAMPLE}
```

**Result:** {VALIDATION_RESULT_1}

### Example 2: {EXAMPLE_ENTITY_2} (Parent Entity)

**SQL Structure:**
- {SQL_STRUCTURE_DESCRIPTION}

**{ORM_FRAMEWORK} Mappings:**
- {ORM_STRUCTURE_DESCRIPTION}

**Result:** {VALIDATION_RESULT_2}

<!--
INSTRUCTIONS:
- Provide 2-3 detailed examples of complex entity validation
- Show both SQL DDL and ORM mappings side-by-side
- Document validation results
-->

---

## Technical Debt Assessment: {TECHNICAL_DEBT_LEVEL}

### Code Smell Analysis:

| Smell | Severity | Finding |
|-------|----------|---------|
| Missing mappings | {MISSING_MAPPINGS_SEVERITY} | {MISSING_MAPPINGS_FINDING} |
| Broken relationships | {BROKEN_RELATIONSHIPS_SEVERITY} | {BROKEN_RELATIONSHIPS_FINDING} |
| Inconsistent patterns | {INCONSISTENT_PATTERNS_SEVERITY} | {INCONSISTENT_PATTERNS_FINDING} |
| Circular dependencies | {CIRCULAR_DEPENDENCIES_SEVERITY} | {CIRCULAR_DEPENDENCIES_FINDING} |
| Legacy code | {LEGACY_CODE_SEVERITY} | {LEGACY_CODE_FINDING} |
| Performance issues | {PERFORMANCE_SEVERITY} | {PERFORMANCE_FINDING} |

### Maintainability Score: {MAINTAINABILITY_SCORE}/10

**Deductions:**
- {DEDUCTION_1}
- {DEDUCTION_2}

**Strengths:**
- {MAINTAINABILITY_STRENGTH_1}
- {MAINTAINABILITY_STRENGTH_2}
- {MAINTAINABILITY_STRENGTH_3}

<!--
INSTRUCTIONS:
- Assess technical debt level (VERY LOW, LOW, MODERATE, HIGH, VERY HIGH)
- Provide maintainability score out of 10
- Document specific deductions and strengths
-->

---

## Conclusion

{CONCLUSION_PARAGRAPH}

### By The Numbers:
- **{METRIC_1}**
- **{METRIC_2}**
- **{METRIC_3}**
- **{METRIC_4}**

### Grade: {OVERALL_GRADE}

### Migration Risk: {MIGRATION_RISK_LEVEL}

{FINAL_VERDICT_PARAGRAPH}

**Final Verdict:** {FINAL_VERDICT}

<!--
INSTRUCTIONS:
- Summarize overall assessment
- Provide key metrics (coverage percentages, counts)
- Assign overall grade (A+, A, B, C, D, F)
- Assess migration risk (LOW, MODERATE, HIGH)
- Provide final verdict on data model quality
-->

---

## Appendix: File Locations

**SQL DDL:**
`{SQL_DDL_DIRECTORY_PATH}`

**{ORM_FRAMEWORK} Mappings:**
`{ORM_MAPPINGS_DIRECTORY_PATH}`
- {ORM_SUBDIRECTORY_1}: {ORM_SUBDIRECTORY_1_DESCRIPTION}
- {ORM_SUBDIRECTORY_2}: {ORM_SUBDIRECTORY_2_DESCRIPTION}

**Full Report:**
`{COMPREHENSIVE_REPORT_PATH}`

**Discrepancies Guide:**
`{DISCREPANCIES_GUIDE_PATH}`

**JSON Data (if applicable):**
`{JSON_REPORT_PATH}`

---

**Report Date:** {GENERATION_DATE}
**Analyst:** {ANALYST_NAME}
**Confidence:** {CONFIDENCE_LEVEL}

<!--
PAGINATION MARKER (if needed):
If this document exceeds 250 lines, end with:
<<CONTINUE file="06-TABLE-VALIDATION-EXECUTIVE-SUMMARY.md" section="SECTION_ID" part=N next="FIRST_WORDS_OF_NEXT_SECTION">>
-->

---

*Generated By LegacyLift AI by CapTech*
*Generated on: {GENERATED_DATE}*