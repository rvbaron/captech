<!--
This is a template for the Comprehensive Table Validation Report.
Replace all {PLACEHOLDER} markers with actual project-specific values.
This document provides exhaustive table-by-table validation for DBAs, data engineers, and architects.
This document is ONLY GENERATED if an ORM framework (Hibernate, NHibernate, Entity Framework) is detected.
-->

<!-- PAGINATION: This document WILL need to be generated in parts (150-250 lines each). -->
<!-- Use the pagination policy to break this into manageable chunks. -->

# Comprehensive Table Validation Report
## SQL DDL vs {ORM_FRAMEWORK} Mapping Analysis

**Date:** {GENERATION_DATE}
**Repository:** {REPOSITORY_NAME}
**Total SQL Tables:** {TOTAL_SQL_TABLES}
**Total {ORM_FRAMEWORK} Mappings:** {TOTAL_ORM_MAPPINGS} (including subdirectories: {SUBDIRECTORY_LIST})

---

## Executive Summary

After systematic validation of all {TOTAL_SQL_TABLES} SQL tables against their {ORM_FRAMEWORK} mappings, the data model demonstrates **{CONSISTENCY_ASSESSMENT}** between the database schema and ORM layer. {EXECUTIVE_SUMMARY_DESCRIPTION}

### Key Findings:
- **{MAPPED_TABLES_COUNT} tables** have {ORM_FRAMEWORK} mappings (including lookup/type tables in subdirectories)
- **{UNMAPPED_TABLES_COUNT} tables** without mappings (primarily {UNMAPPED_CATEGORIES})
- **{ORM_WITHOUT_TABLES_COUNT} {ORM_FRAMEWORK} mappings** reference views or external tables not in the main schema
- **All core business entities** are {CORE_ENTITIES_STATUS}

<!--
CITATION REQUIREMENT:
Every table, column, and mapping mentioned must cite the source file and line number.
- SQL tables → [📄](path/to/table.sql:line)
- ORM mappings → [📄](path/to/Entity.hbm.xml:line) or [📄](path/to/EntityClass.cs:line)
-->

---

## Core Entities Analysis (DETAILED)

<!--
INSTRUCTIONS:
Provide detailed analysis for EACH core entity (typically 10-15 entities).
For each entity, document:
1. SQL table structure (columns, PK, FK)
2. ORM mapping structure (properties, associations, collections)
3. Column-by-column validation table
4. Relationship validation
5. Status assessment (PERFECT MATCH, PARTIAL, MISSING)
-->

### 1. {CORE_ENTITY_1_NAME}
**Status:** {ENTITY_1_STATUS}

**SQL Table:** `{ENTITY_1_SQL_TABLE_NAME}`
- **Columns:** {ENTITY_1_COLUMN_COUNT}
- **Primary Key:** {ENTITY_1_PRIMARY_KEY}
- **Foreign Keys:** {ENTITY_1_FK_COUNT} ({ENTITY_1_FK_DESCRIPTION})

**{ORM_FRAMEWORK} Mapping:** `{ENTITY_1_MAPPING_FILE}`
- **Properties:** {ENTITY_1_PROPERTY_COUNT} scalar properties
- **Many-to-One:** {ENTITY_1_MANY_TO_ONE_COUNT} ({ENTITY_1_MANY_TO_ONE_LIST})
- **One-to-One:** {ENTITY_1_ONE_TO_ONE_COUNT} ({ENTITY_1_ONE_TO_ONE_LIST})
- **One-to-Many Sets:** {ENTITY_1_ONE_TO_MANY_COUNT} ({ENTITY_1_ONE_TO_MANY_LIST})

**Column Mapping:**
| SQL Column | {ORM_FRAMEWORK} Property | Type Match | Notes |
|------------|-------------------------|------------|-------|
| {COL_1_SQL_NAME} | {COL_1_ORM_NAME} | {COL_1_MATCH} | {COL_1_NOTES} |
| {COL_2_SQL_NAME} | {COL_2_ORM_NAME} | {COL_2_MATCH} | {COL_2_NOTES} |
<!-- Repeat for all columns -->

**Relationships:** {ENTITY_1_RELATIONSHIPS_DESCRIPTION}

<!-- Cite SQL DDL file: [📄](path/to/Entity1Table.sql:line) -->
<!-- Cite ORM mapping file: [📄](path/to/Entity1.hbm.xml:line) -->

---

### 2. {CORE_ENTITY_2_NAME}
**Status:** {ENTITY_2_STATUS}

<!-- Repeat the same structure as Entity 1 -->
<!-- Document SQL table, ORM mapping, column mapping, relationships -->
<!-- Include citations for every claim -->

---

<!-- Continue for all core entities (10-15 entities) -->

<!--
PAGINATION MARKER:
After documenting 3-5 core entities (or ~200 lines), use:
<<CONTINUE file="06-TABLE-VALIDATION-COMPREHENSIVE-REPORT.md" section="CORE_ENTITIES" part=1 next="### 6. {NEXT_ENTITY_NAME}">>
-->

---

## Lookup/Type Tables Analysis

All type tables are properly mapped in subdirectories:
- **`{TYPE_SUBDIRECTORY_1}`** - {TYPE_TABLE_COUNT_1} type tables
- **`{TYPE_SUBDIRECTORY_2}`** - {TYPE_TABLE_COUNT_2} type tables

### Example Type Table Mappings:

#### {TYPE_TABLE_1_NAME}
**Status:** {TYPE_TABLE_1_STATUS}
- Location: `{TYPE_TABLE_1_MAPPING_FILE}`
- All {TYPE_TABLE_1_COLUMN_COUNT} columns mapped including:
  - {TYPE_TABLE_1_COLUMN_1}
  - {TYPE_TABLE_1_COLUMN_2}
  - {TYPE_TABLE_1_COLUMN_3}
  - {TYPE_TABLE_1_COLUMN_4}

<!-- Cite mapping file: [📄](path/to/TypeTable1.hbm.xml:line) -->

#### {TYPE_TABLE_2_NAME}, {TYPE_TABLE_3_NAME}, {TYPE_TABLE_4_NAME}, etc.
All type tables follow the same pattern with complete mappings.

---

## Tables Without {ORM_FRAMEWORK} Mappings ({UNMAPPED_COUNT} tables)

These tables fall into specific categories:

### 1. {UNMAPPED_CATEGORY_1_NAME} ({UNMAPPED_CATEGORY_1_COUNT} tables)
{UNMAPPED_CATEGORY_1_DESCRIPTION}
- {UNMAPPED_TABLE_1}
- {UNMAPPED_TABLE_2}
- {UNMAPPED_TABLE_3}
<!-- List all tables in this category -->

**Reason:** {UNMAPPED_CATEGORY_1_REASON}

### 2. {UNMAPPED_CATEGORY_2_NAME} ({UNMAPPED_CATEGORY_2_COUNT} tables)
{UNMAPPED_CATEGORY_2_DESCRIPTION}
- {UNMAPPED_TABLE_4}
- {UNMAPPED_TABLE_5}
- {UNMAPPED_TABLE_6}
<!-- List all tables in this category -->

**Reason:** {UNMAPPED_CATEGORY_2_REASON}

<!-- Continue for all unmapped table categories -->
<!-- Common categories: Quartz Scheduler, External Integration, Temporary/Working, Specialized/Utility -->

---

## {ORM_FRAMEWORK} Mappings Without SQL Tables ({ORM_WITHOUT_TABLES_COUNT} items)

### Views ({VIEW_COUNT}):
- {VIEW_1_NAME}
- {VIEW_2_NAME}

**Note:** These are SQL views, not tables. Views are properly mapped for read-only access.

### External/Lookup ({EXTERNAL_COUNT}):
- {EXTERNAL_1_NAME}
- {EXTERNAL_2_NAME}
<!-- List all external mappings -->

**Reason:** {EXTERNAL_REASON}

---

## Type Mapping Patterns

### Custom {ORM_FRAMEWORK} UserTypes:
The application uses custom types for data conversion:

| Custom Type | Purpose | SQL Type |
|------------|---------|----------|
| {CUSTOM_TYPE_1} | {CUSTOM_TYPE_1_PURPOSE} | {CUSTOM_TYPE_1_SQL_TYPE} |
| {CUSTOM_TYPE_2} | {CUSTOM_TYPE_2_PURPOSE} | {CUSTOM_TYPE_2_SQL_TYPE} |
| {CUSTOM_TYPE_3} | {CUSTOM_TYPE_3_PURPOSE} | {CUSTOM_TYPE_3_SQL_TYPE} |
<!-- Add more custom types -->

<!-- Cite custom type implementations: [📄](path/to/CustomType.cs:line) -->

### Numeric Type Mappings:
| SQL Type | {ORM_FRAMEWORK} Type | Notes |
|----------|---------------------|-------|
| {SQL_NUMERIC_TYPE_1} | {ORM_NUMERIC_TYPE_1} | {NUMERIC_TYPE_NOTES_1} |
| {SQL_NUMERIC_TYPE_2} | {ORM_NUMERIC_TYPE_2} | {NUMERIC_TYPE_NOTES_2} |
<!-- Add more numeric type mappings -->

---

## Relationship Patterns

### Standard Pattern:
1. **Parent-to-Child:** {PARENT_TO_CHILD_DESCRIPTION}
2. **Child-to-Parent:** {CHILD_TO_PARENT_DESCRIPTION}
3. **Bidirectional:** {BIDIRECTIONAL_DESCRIPTION}

### Example ({RELATIONSHIP_EXAMPLE_ENTITY_1} ↔ {RELATIONSHIP_EXAMPLE_ENTITY_2}):
```xml
<!-- In {RELATIONSHIP_EXAMPLE_MAPPING_1} -->
{RELATIONSHIP_EXAMPLE_CODE_1}

<!-- In {RELATIONSHIP_EXAMPLE_MAPPING_2} -->
{RELATIONSHIP_EXAMPLE_CODE_2}
```

<!-- Cite relationship mapping files: [📄](path/to/Mapping1.hbm.xml:line) [📄](path/to/Mapping2.hbm.xml:line) -->

---

## Constraint Validation

### Primary Keys:
{PRIMARY_KEY_VALIDATION_DESCRIPTION}

### Foreign Keys:
{FOREIGN_KEY_VALIDATION_DESCRIPTION}

### Unique Constraints:
{UNIQUE_CONSTRAINT_VALIDATION_DESCRIPTION}

### NOT NULL Constraints:
{NOT_NULL_VALIDATION_DESCRIPTION}
**Impact:** {NOT_NULL_IMPACT_DESCRIPTION}

---

## Significant Findings

### 1. Audit Trail Pattern
Every core entity has:
- {AUDIT_TRAIL_DESCRIPTION}
All properly mapped, with {AUDIT_TRAIL_UPDATE_FIELD} as {AUDIT_TRAIL_UPDATE_ELEMENT}.

### 2. Legacy System Integration
Multiple "Old" columns for migration from legacy systems:
- {LEGACY_COLUMN_PATTERN_DESCRIPTION}
All properly maintained in mappings.

### 3. Soft Delete / Date Ranges
Status history pattern used extensively:
- {TEMPORAL_PATTERN_DESCRIPTION}
- Supports temporal queries and audit requirements

### 4. Circular Dependency Handling
{CIRCULAR_DEPENDENCY_DESCRIPTION}
- {CIRCULAR_DEPENDENCY_SOLUTION}
- **Smart workaround** to avoid {ORM_FRAMEWORK} circular initialization issues

### 5. Optimistic Locking
All main entities use `{OPTIMISTIC_LOCKING_MECHANISM}` for optimistic locking:
```xml
{OPTIMISTIC_LOCKING_EXAMPLE_CODE}
```
This prevents concurrent modification conflicts.

<!-- Cite implementations for each finding -->

---

## Data Model Health: {HEALTH_ASSESSMENT}

### Strengths:
1. **{STRENGTH_1}**
2. **{STRENGTH_2}**
3. **{STRENGTH_3}**
4. **{STRENGTH_4}**
5. **{STRENGTH_5}**
6. **{STRENGTH_6}**
7. **{STRENGTH_7}**

### Areas for Attention:
1. **{ATTENTION_AREA_1}**
2. **{ATTENTION_AREA_2}**
3. **{ATTENTION_AREA_3}**

---

## Conclusion

{CONCLUSION_PARAGRAPH}

**Overall Grade: {OVERALL_GRADE}**

**Migration Readiness:** {MIGRATION_READINESS}

---

## Appendix: File Locations

### SQL DDL:
`{SQL_DDL_PATH}`

### {ORM_FRAMEWORK} Mappings:
`{ORM_MAPPINGS_PATH}`
- {ORM_SUBDIRECTORY_1}: {ORM_SUBDIRECTORY_1_DESCRIPTION}
- {ORM_SUBDIRECTORY_2}: {ORM_SUBDIRECTORY_2_DESCRIPTION}

### Validation Script:
`{VALIDATION_SCRIPT_PATH}` (automated validation tool)

### JSON Report:
`{JSON_REPORT_PATH}` (machine-readable results)

---

**Report Generated:** {GENERATION_DATE}
**Analysis Method:** {ANALYSIS_METHOD}
**Confidence Level:** {CONFIDENCE_LEVEL}

<!--
PAGINATION:
This document will be generated in multiple parts.
Each part should end with a continuation marker:
<<CONTINUE file="06-TABLE-VALIDATION-COMPREHENSIVE-REPORT.md" section="SECTION_ID" part=N next="FIRST_WORDS">>
-->

---

*Generated By LegacyLift AI by CapTech*
*Generated on: {GENERATED_DATE}*