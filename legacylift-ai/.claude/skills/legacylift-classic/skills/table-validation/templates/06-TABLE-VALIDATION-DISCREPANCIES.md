<!--
This is a template for the Table Validation Discrepancies Guide.
Replace all {PLACEHOLDER} markers with actual project-specific values.
This document explains apparent discrepancies between SQL DDL and ORM mappings.
This document is ONLY GENERATED if an ORM framework (Hibernate, NHibernate, Entity Framework) is detected.
Purpose: Help stakeholders understand that most "discrepancies" are intentional design patterns, not bugs.
-->

<!-- PAGINATION: This document may need to be generated in parts (150-250 lines each) if content is large. -->

# Table Validation Discrepancies Guide
## Understanding "Mismatches" Between SQL and {ORM_FRAMEWORK}

**System:** {SYSTEM_NAME}
**Date:** {GENERATION_DATE}

---

## Overview

This document explains apparent "discrepancies" between SQL DDL and {ORM_FRAMEWORK} mappings. **Important:** These are NOT bugs or issues - they are **intentional design patterns** that add value through business logic encapsulation and type safety.

---

## Categories of "Discrepancies"

### 1. Custom Type Mappings (By Design) ✅

{ORM_FRAMEWORK} uses custom UserTypes to add business logic at the ORM layer:

| SQL Type | {ORM_FRAMEWORK} Type | Purpose | Benefit |
|----------|---------------------|---------|---------|
| {SQL_TYPE_1} | {CUSTOM_TYPE_1} | {CUSTOM_TYPE_1_PURPOSE} | {CUSTOM_TYPE_1_BENEFIT} |
| {SQL_TYPE_2} | {CUSTOM_TYPE_2} | {CUSTOM_TYPE_2_PURPOSE} | {CUSTOM_TYPE_2_BENEFIT} |
| {SQL_TYPE_3} | {CUSTOM_TYPE_3} | {CUSTOM_TYPE_3_PURPOSE} | {CUSTOM_TYPE_3_BENEFIT} |
<!-- Add more custom type mappings -->

**Example:**
```sql
-- SQL
{CUSTOM_TYPE_SQL_EXAMPLE}
```

```xml
<!-- {ORM_FRAMEWORK} -->
{CUSTOM_TYPE_ORM_EXAMPLE}
```

**Why?** {CUSTOM_TYPE_WHY}

<!-- Cite custom type implementation: [📄](path/to/CustomType.cs:line) -->

---

### 2. Property Name Differences (Intentional) ℹ️

Some properties renamed for clarity in {PROGRAMMING_LANGUAGE} code:

| SQL Column | {ORM_FRAMEWORK} Property | Reason |
|------------|-------------------------|--------|
| {SQL_COL_1} | {ORM_PROP_1} | {RENAME_REASON_1} |
| {SQL_COL_2} | {ORM_PROP_2} | {RENAME_REASON_2} |

**Example ({EXAMPLE_ENTITY}):**
```sql
-- SQL DDL
{PROPERTY_RENAME_SQL_EXAMPLE}
```

```xml
<!-- {ORM_FRAMEWORK} Mapping -->
{PROPERTY_RENAME_ORM_EXAMPLE}
```

**Impact:** None - mapping explicitly connects property to column. {PROGRAMMING_LANGUAGE} code uses more intuitive names.

<!-- Cite SQL DDL: [📄](path/to/table.sql:line) -->
<!-- Cite ORM mapping: [📄](path/to/Entity.hbm.xml:line) -->

---

### 3. Timestamp vs Property (Optimistic Locking) ✅

`{UPDATE_DATE_COLUMN}` appears to be "missing" from properties but is actually mapped as `{TIMESTAMP_ELEMENT}`:

**SQL:**
```sql
{TIMESTAMP_SQL_EXAMPLE}
```

**{ORM_FRAMEWORK}:**
```xml
{TIMESTAMP_ORM_EXAMPLE}
```

**Why Special?** The `{TIMESTAMP_ELEMENT}` element:
1. Automatically updates on every save
2. Enables optimistic locking (prevents concurrent modification conflicts)
3. Database-managed (source="db")

This is **superior** to a regular property - it's a concurrency control mechanism.

<!-- Cite timestamp implementation: [📄](path/to/Entity.hbm.xml:line) -->

---

### 4. Foreign Keys as Many-to-One (Standard ORM) ✅

Foreign key columns appear as many-to-one associations instead of scalar properties:

**SQL:**
```sql
-- Foreign key column
{FK_SQL_EXAMPLE}
```

**{ORM_FRAMEWORK}:**
```xml
<!-- Many-to-one association -->
{FK_ORM_EXAMPLE}
```

**Why?** This is **standard ORM practice**:
- Type-safe navigation: `{NAVIGATION_EXAMPLE}`
- Automatic join handling
- Lazy loading support
- Relationship integrity

You can still access the FK value if needed: The generated class typically includes `{FK_GETTER_METHOD}` method.

<!-- Cite FK constraint: [📄](path/to/table.sql:line) -->
<!-- Cite many-to-one mapping: [📄](path/to/Entity.hbm.xml:line) -->

---

### 5. Circular Dependency Workaround (Smart Design) ✅

**{CIRCULAR_DEPENDENCY_ENTITY}** has a special case:

**{ORM_FRAMEWORK} Mapping:**
```xml
{CIRCULAR_DEPENDENCY_EXAMPLE}
```

**Comment in {MAPPING_FORMAT}:** "{CIRCULAR_DEPENDENCY_COMMENT}"

**What's happening?**
- {CIRCULAR_DEPENDENCY_PATH_DESCRIPTION}
- Mapping this as many-to-one would create initialization deadlock
- Solution: Map as scalar property instead

**Impact:** Acceptable trade-off. You can still navigate:
```{PROGRAMMING_LANGUAGE_EXTENSION}
{CIRCULAR_DEPENDENCY_WORKAROUND_CODE}
```

This is a **known {ORM_FRAMEWORK} pattern** for resolving circular dependencies.

<!-- Cite circular dependency workaround: [📄](path/to/Entity.hbm.xml:line) -->

---

## Non-Issues Explained

### "Columns in SQL but not in {MAPPING_FORMAT}"

**Reality:** Most of these ARE mapped, just in different ways:

#### Case 1: Mapped as timestamp
```
SQL: {UPDATE_DATE_COLUMN}
{MAPPING_FORMAT}: {TIMESTAMP_ELEMENT_EXAMPLE}
```
**Status:** ✅ Mapped (automated script missed this)

#### Case 2: Mapped as many-to-one
```
SQL: {FK_COLUMN_EXAMPLE}
{MAPPING_FORMAT}: {MANY_TO_ONE_EXAMPLE}
```
**Status:** ✅ Mapped (automated script looked for property, not association)

#### Case 3: Mapped with different name
```
SQL: {SQL_COLUMN_EXAMPLE}
{MAPPING_FORMAT}: {ORM_PROPERTY_EXAMPLE}
```
**Status:** ✅ Mapped (automated script didn't match property to column)

---

## Tables Without Mappings (By Design)

### {UNMAPPED_CATEGORY_1_NAME} ({UNMAPPED_CATEGORY_1_COUNT}) - EXPECTED ✅

```
{UNMAPPED_CATEGORY_1_TABLE_LIST}
```

**Reason:** {UNMAPPED_CATEGORY_1_REASON}
**Action Required:** None - this is standard

### {UNMAPPED_CATEGORY_2_NAME} ({UNMAPPED_CATEGORY_2_COUNT}) - BY DESIGN ✅

```
{UNMAPPED_CATEGORY_2_TABLE_LIST}
```

**Reason:** {UNMAPPED_CATEGORY_2_REASON}
**Access Method:** {UNMAPPED_CATEGORY_2_ACCESS_METHOD}
**Action Required:** None - intentional architecture

### {UNMAPPED_CATEGORY_3_NAME} ({UNMAPPED_CATEGORY_3_COUNT}) - EXPECTED ✅

```
{UNMAPPED_CATEGORY_3_TABLE_LIST}
```

**Reason:** {UNMAPPED_CATEGORY_3_REASON}
**Action Required:** None - temporary by design

### {UNMAPPED_CATEGORY_4_NAME} ({UNMAPPED_CATEGORY_4_COUNT}) - ACCEPTABLE ✅

```
{UNMAPPED_CATEGORY_4_TABLE_LIST}
```

**Reason:** {UNMAPPED_CATEGORY_4_REASON}
**Action Required:** None - appropriate for use case

<!-- Common categories: Quartz Scheduler, External Integration, Temporary/Working, Specialized -->

---

## {MAPPING_FORMAT} Without Tables ({ORM_WITHOUT_TABLES_COUNT})

### Views ({VIEW_COUNT}) - CORRECT ✅
```
{VIEW_LIST}
```

**Reason:** These are SQL views, not tables
**Status:** Correctly mapped for read-only access

### External/Configuration ({EXTERNAL_COUNT}) - INVESTIGATION NEEDED ⚠️
```
{EXTERNAL_MAPPING_LIST}
```

**Possible Reasons:**
1. External database tables
2. Configuration tables
3. Deprecated mappings
4. {MAPPING_FORMAT} file issues

**Recommendation:** Review if these are actively used.

---

## Custom UserType Details

### {CUSTOM_TYPE_1_NAME}
```{PROGRAMMING_LANGUAGE_EXTENSION}
{CUSTOM_TYPE_1_IMPLEMENTATION}
```

**Benefit:** {CUSTOM_TYPE_1_BENEFIT_DESCRIPTION}

### {CUSTOM_TYPE_2_NAME}
```{PROGRAMMING_LANGUAGE_EXTENSION}
{CUSTOM_TYPE_2_IMPLEMENTATION}
```

**Benefit:** {CUSTOM_TYPE_2_BENEFIT_DESCRIPTION}

### {CUSTOM_TYPE_3_NAME}
```{PROGRAMMING_LANGUAGE_EXTENSION}
{CUSTOM_TYPE_3_IMPLEMENTATION}
```

**Benefit:** Type safety, clearer code:
```{PROGRAMMING_LANGUAGE_EXTENSION}
{CUSTOM_TYPE_3_USAGE_EXAMPLE}
```

### {CUSTOM_TYPE_4_NAME}
```{PROGRAMMING_LANGUAGE_EXTENSION}
{CUSTOM_TYPE_4_IMPLEMENTATION}
```

**Benefit:** Compile-time checking, IDE autocomplete, refactoring support.

<!-- Cite custom type implementations: [📄](path/to/CustomType.cs:line) -->

---

## Validation Checklist

When reviewing a "discrepancy":

- [ ] Is it a custom UserType? (Expected, adds value)
- [ ] Is the column mapped as many-to-one? (Standard ORM practice)
- [ ] Is it mapped as `{TIMESTAMP_ELEMENT}`? (Concurrency control feature)
- [ ] Is the property name different? (Check column attribute)
- [ ] Is it in a table without mapping? (Check if Quartz/integration/temp)
- [ ] Is it a circular dependency workaround? (Documented in {MAPPING_FORMAT})

---

## Real Issues vs Non-Issues

### ✅ NOT Issues (False Positives):

1. **Custom type mappings** - Business logic encapsulation
2. **Many-to-one for FKs** - Standard ORM practice
3. **Timestamp element** - Optimistic locking feature
4. **Property name differences** - Documented in column attribute
5. **Unmapped {UNMAPPED_CATEGORY_1_NAME} tables** - Framework-managed
6. **Unmapped {UNMAPPED_CATEGORY_2_NAME} tables** - By design
7. **Circular dependency workarounds** - Documented pattern

### ⚠️ Items to Review (Minor):

1. **{REVIEW_ITEM_1}** - {REVIEW_ITEM_1_DESCRIPTION}
2. **{REVIEW_ITEM_2}** - {REVIEW_ITEM_2_DESCRIPTION}
3. **nullable vs NOT NULL** - Some minor inconsistencies (DB enforces)

### ❌ Real Issues Found:

**{REAL_ISSUES_DESCRIPTION}** - {REAL_ISSUES_DETAILS}

<!--
INSTRUCTIONS:
- If no real issues found, state "NONE - All 'discrepancies' are intentional design patterns."
- If real issues found, list them with severity and recommendations
-->

---

## Conclusion

What initially appeared as "discrepancies" are actually:
1. **Value-added features** (custom types, optimistic locking)
2. **Standard ORM patterns** (many-to-one, bidirectional relationships)
3. **Architectural decisions** (external table handling, circular dependency resolution)
4. **Framework integration** ({FRAMEWORK_INTEGRATION_EXAMPLES})

**Data Model Health:** {HEALTH_ASSESSMENT}

**Action Required:** {ACTION_REQUIRED}

---

## Reference: Common Patterns

### Pattern 1: Audit Trail
```xml
{AUDIT_TRAIL_PATTERN_EXAMPLE}
```

### Pattern 2: Temporal Data
```xml
{TEMPORAL_DATA_PATTERN_EXAMPLE}
```

### Pattern 3: Parent-Child
```xml
{PARENT_CHILD_PATTERN_EXAMPLE}
```

<!-- Cite pattern implementations -->

---

**Document Version:** 1.0
**Last Updated:** {GENERATION_DATE}
**Status:** {DOCUMENT_STATUS}

<!--
PAGINATION MARKER (if needed):
If this document exceeds 250 lines, end with:
<<CONTINUE file="06-TABLE-VALIDATION-DISCREPANCIES.md" section="SECTION_ID" part=N next="FIRST_WORDS_OF_NEXT_SECTION">>
-->

---

*Generated By LegacyLift AI by CapTech*
*Generated on: {GENERATED_DATE}*