---
name: repo-summary-generator
description: Analyzes all generated documentation in a repository and produces a comprehensive summary with metrics, statistics, and facts at a glance for presentations and reports.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Task
---

# Repository Summary Generator

This skill analyzes all generated LegacyLift documentation in a repository and produces a comprehensive summary document with metrics, statistics, and "Facts at a Glance" information suitable for executive presentations, project reports, and stakeholder communication.

## Instructions

The repo-summary-generator skill systematically analyzes the documentation portfolio in the `legacylift-docs/` folder and produces a single comprehensive summary file:

1. **13-REPOSITORY-SUMMARY.md** - Documentation portfolio metrics and statistics (15-20 min read)

## Examples

```
Generate a repository summary for the documentation portfolio.
```

```
Use repo-summary-generator to create facts at a glance for the project.
```

```
/legacylift-classic:repo-summary-generator
```

## Documentation Process

The skill follows a systematic 5-phase approach:

### Phase 1: Documentation Discovery (Inventory the Portfolio)

1. **Scan legacylift-docs/ Directory**:
   - Count all `.md` markdown files: `ls -1 *.md | wc -l`
   - Calculate total file size: `du -sh *.md` (human-readable format like "3.2M")
   - Count total lines of documentation: `wc -l *.md | tail -1`
   - Count PDF files if present: `ls -1 *.pdf 2>/dev/null | wc -l`
   - Identify document categories (core suite, use cases, user stories, etc.)

2. **Extract Document Metadata**:
   - Reading time estimates from each document (grep for "Reading Time" in docs)
   - Document types and purposes (identify from file name prefixes 00-12)
   - Domains covered (extract from use case/user story file names)
   - PDF availability (conditional - only mention if PDFs present)
   - Version/generation dates if available

### Phase 2: Content Analysis (Extract Metrics)

1. **Count Requirements & Specifications**:
   - Use cases: `grep -h "^### UC-" 08-USE-CASES-*.md | wc -l`
   - User stories: `grep -h "^### US-" 11-USER-STORIES-*.md | wc -l`
   - Epics: `grep -h "^## Epic [0-9]" 11-USER-STORIES-*.md | wc -l`
   - Business rules: `grep -Eh "^### (BR-|FR-)" 03-BUSINESS-RULES-*.md | wc -l`
   - Functional requirements: `grep -Eh "^### FR-" 03-BUSINESS-RULES-*.md | wc -l`

2. **Count Technical Documentation**:
   - Tables documented: `grep -h "^### Table: " 12-DATA-DICTIONARY-*.md | wc -l`
   - API endpoints: Extract from API documentation
   - Domains covered: Count unique domain documents
   - Data dictionaries: Count 12-DATA-DICTIONARY-*.md files

3. **Count Quality Metrics**:
   - Citations: `grep -o '\[📄\]' *.md | wc -l`
   - Mermaid diagrams: `grep -c "mermaid" *.md | cut -d: -f2 | awk '{sum+=$1} END {print sum}'`
   - Cross-references: Count internal document links
   - Validation reports: Count validation documents

### Phase 3: Statistical Aggregation (Organize Data)

1. **Group by Document Category**:
   - Core documentation suite (00-05)
   - Validation reports (06-07)
   - Use cases (08)
   - Gap analysis (10)
   - User stories (11)
   - Data dictionaries (12)

2. **Calculate Aggregated Metrics**:
   - Total documents by category
   - Total lines by category
   - Total reading time by category
   - Domain coverage completeness

3. **Technology Stack Analysis**:
   - Read `01-SYSTEM-ARCHITECTURE.md` to detect primary language and frameworks
   - Read `00-EXECUTIVE-SUMMARY.md` for high-level technology mentions
   - Detect validation type from validation report titles (if present)
   - Identify API style (REST, GraphQL, gRPC, SOAP) from API documentation
   - Extract code example languages from citations and code blocks
   - Determine model file types from architecture documentation
   - **Use detected technology to fill placeholders**:
     - `{PRIMARY_LANGUAGE}`: Main language (Java 11, C# .NET 6, Python 3.12, etc.)
     - `{API_STYLE}`: API architecture (REST, GraphQL, gRPC, etc.)
     - `{VALIDATION_TYPE}`: Validation approach (ORM-to-DDL, EF-to-SQL, Schema validation)
     - `{CODE_EXAMPLE_LANGUAGES}`: Languages in examples (Java/SQL/XML, C#/SQL/JSON, etc.)
     - `{MODEL_FILES_TYPE}`: Model type (Java classes, C# classes, Python models, etc.)
   - **Fallback to generic terms if technology unclear** (e.g., "Primary language", "API endpoints", "Data validation")

### Phase 4: Document Generation (Create Summary)

**⚠️ CRITICAL: Use the template structure exactly. Fill in all metrics with actual data from Phase 1-3 analysis.**

**⚠️ TECHNOLOGY-AGNOSTIC REQUIREMENT: The skill must work for any technology stack (Java, .NET, Python, Node.js, etc.). Detect technology from architecture docs and fill technology-specific placeholders accordingly.**

1. **Write Document Using Template**:
   - Use `13-REPOSITORY-SUMMARY.md` template
   - Fill in all statistics and metrics
   - **Detect and fill technology-specific placeholders**:
     - Read `01-SYSTEM-ARCHITECTURE.md` "Technology Stack" section for primary language/frameworks
     - Extract validation type from report names (e.g., "Hibernate ORM-to-DDL" vs "Entity Framework validation")
     - Use generic fallbacks if technology unclear (e.g., "Primary language", "Data validation")
   - Create tables with actual counts
   - Include domain breakdown with details

2. **Structure Sections**:
   - Documentation Portfolio Overview
   - Document Breakdown by Category
   - Content Metrics (use cases, user stories, business rules)
   - Quality & Verification Metrics
   - Technology Stack Documented
   - Business Value Delivered
   - Knowledge Transfer Metrics
   - Documentation Statistics Summary
   - Deliverables Ready for Use
   - Key Highlights

3. **Use Visual Elements**:
   - Tables for easy data consumption
   - Emoji icons for visual appeal (📊 📚 ✅ 🎯 etc.)
   - Section headers with clear hierarchy
   - Bullet points for readability

### Phase 5: Review & Polish (Quality Assurance)

1. **Verify All Metrics**:
   - Double-check all counts are accurate
   - Ensure no placeholder text remains
   - Verify all percentages and calculations
   - Confirm document list completeness

2. **Add Document Footer**:
   - Include generation date
   - Add "Generated by LegacyLift AI" footer

3. **Save to Repository**:
   - Place in `legacylift-docs/` directory
   - Filename: `13-REPOSITORY-SUMMARY.md`

---

## Key Features

### 📊 **Comprehensive Metrics**
- Total documents generated with sizes and line counts
- Use cases, user stories, epics, and business rules counted
- Citation coverage and diagram counts
- Reading time aggregations

### 📚 **Category Breakdown**
- Documents organized by type (core, use cases, user stories, etc.)
- Lines of documentation per category
- Reading time estimates per category
- Domain coverage analysis

### 🎯 **Quality Indicators**
- Citation counts for verification
- Diagram counts for visual documentation
- Validation report coverage
- Cross-reference completeness

### 🏗️ **Technology Coverage**
- Frameworks and libraries documented
- Technology layers covered
- Architecture patterns identified

### 💼 **Business Value**
- Modernization readiness metrics
- Stakeholder support documentation
- Sprint planning readiness
- Knowledge transfer metrics

---

## Output Quality Standards

Generated repository summary includes:

✅ **Accurate Statistics** - All counts verified against actual documentation
✅ **Organized Presentation** - Clear tables and sections for easy consumption
✅ **Visual Appeal** - Emoji icons and formatting for presentations
✅ **Complete Coverage** - All document types and categories included
✅ **Business Context** - Metrics tied to business value and modernization
✅ **Ready for Presentations** - Formatted for PowerPoint/slide deck use
✅ **Actionable Insights** - Deliverables and next steps clearly identified
✅ **Document Footer** - Professional footer with generation attribution

---

## Example Output Structure

```
project-root/
└── legacylift-docs/
    ├── 00-EXECUTIVE-SUMMARY.md
    ├── 01-SYSTEM-ARCHITECTURE.md
    ├── ...
    ├── 12-DATA-DICTIONARY-POINTS.md
    └── 13-REPOSITORY-SUMMARY.md  ← Generated by this skill
```

---

## Technical Implementation

This skill uses Claude Code's capabilities:

- **Bash Commands**: File listing, counting, size calculation
- **Grep/Pattern Matching**: Extract counts from markdown files
- **Read Tool**: Examine document content and metadata
- **Template System**: Structured repository summary format
- **Statistical Analysis**: Aggregate metrics across documentation portfolio

---

## Success Criteria

Documentation is considered complete when:

✅ All markdown files in legacylift-docs/ are counted
✅ All metrics (use cases, user stories, business rules) are extracted
✅ All document categories are identified and summarized
✅ Citation and diagram counts are accurate
✅ **Technology stack is detected from architecture docs and placeholders filled appropriately**
✅ **Technology-specific terms match actual codebase (not hard-coded assumptions)**
✅ Reading time aggregations are calculated
✅ Business value metrics are included
✅ Document follows template structure exactly
✅ All tables are filled with actual data (no placeholders)
✅ Professional footer is included
✅ **Document works for any technology stack (Java, .NET, Python, Node.js, etc.)**

---

## Skill Execution

When this skill is invoked, I will:

1. **Scan Documentation Portfolio**
   - List all markdown files in legacylift-docs/
   - Calculate sizes and line counts
   - Identify document types

2. **Extract Metrics**
   - Count use cases, user stories, epics, business rules
   - Count tables, API endpoints, domains
   - Count citations, diagrams, cross-references

3. **Aggregate Statistics**
   - Group by document category
   - Calculate totals and subtotals
   - Compute reading time estimates

**3.5. Detect Technology Stack** (Technology-Agnostic Approach)
   - Read `01-SYSTEM-ARCHITECTURE.md` to detect:
     - Primary programming language (Java, C#, Python, TypeScript, etc.)
     - API architecture style (REST, GraphQL, gRPC, SOAP)
     - Frontend framework (React, Angular, Vue, JSP, Razor, etc.)
     - Backend framework (Spring, ASP.NET Core, FastAPI, Express, etc.)
     - ORM/Data access (Hibernate, Entity Framework, SQLAlchemy, Prisma, etc.)
     - Database (SQL Server, PostgreSQL, MongoDB, Oracle, etc.)
   - Read validation reports to detect validation type:
     - File name pattern: `06-TABLE-VALIDATION-*` → extract validation approach
     - Content: Look for "Hibernate", "Entity Framework", "NHibernate", etc.
   - **Examples of Technology Detection**:
     ```
     Java/Spring Stack:
       {PRIMARY_LANGUAGE} = "Java 11"
       {API_STYLE} = "REST"
       {VALIDATION_TYPE} = "ORM-to-DDL"
       {CODE_EXAMPLE_LANGUAGES} = "Java, SQL, XML"
       {MODEL_FILES_TYPE} = "Java classes"

     .NET/C# Stack:
       {PRIMARY_LANGUAGE} = "C# .NET 6"
       {API_STYLE} = "REST"
       {VALIDATION_TYPE} = "Entity Framework-to-SQL"
       {CODE_EXAMPLE_LANGUAGES} = "C#, SQL, JSON"
       {MODEL_FILES_TYPE} = "C# classes"

     Python Stack:
       {PRIMARY_LANGUAGE} = "Python 3.12"
       {API_STYLE} = "REST"
       {VALIDATION_TYPE} = "SQLAlchemy-to-SQL"
       {CODE_EXAMPLE_LANGUAGES} = "Python, SQL, YAML"
       {MODEL_FILES_TYPE} = "Python models"

     Generic Fallback (if unclear):
       {PRIMARY_LANGUAGE} = "Primary language"
       {API_STYLE} = "API"
       {VALIDATION_TYPE} = "Data model validation"
       {CODE_EXAMPLE_LANGUAGES} = "Multiple languages"
       {MODEL_FILES_TYPE} = "Source files"
     ```

4. **Generate Summary Document**
   - Use 13-REPOSITORY-SUMMARY.md template
   - Fill in all metrics and statistics
   - Create organized tables and sections
   - Add visual elements and formatting

5. **Review & Polish**
   - Verify all counts are accurate
   - Ensure professional presentation
   - Add footer and metadata

6. **Deliver Complete Summary**
   - 13-REPOSITORY-SUMMARY.md in markdown format
   - Placed in `legacylift-docs/` directory
   - Ready for PowerPoint presentations and reports
   - Suitable for executive stakeholders

---

## Supporting Files & Templates

This skill uses supporting files in the `templates/` directory:

| Template File | Purpose | Usage |
|---------------|---------|-------|
| **[13-REPOSITORY-SUMMARY.md](./templates/13-REPOSITORY-SUMMARY.md)** | Structure for repository summary | Guides metric organization, table formats, and content sections |

### How Templates Are Used

During skill execution, I (Claude) will:

1. **Reference Template**: Read the repository summary template
2. **Extract Structure**: Use the template's sections and table formats
3. **Fill with Analysis**: Replace placeholders with actual metrics from documentation analysis
4. **Maintain Consistency**: Ensure professional formatting throughout
5. **Adapt as Needed**: Customize sections based on actual documentation portfolio

---

## Related Skills

This skill complements other LegacyLift skills:

- **fact-graph**: Provides entity/relation/fact statistics for summary
- **exec-summary-generator**: Creates 00-EXECUTIVE-SUMMARY.md (referenced in portfolio)
- **use-case-generator**: Creates use cases counted in summary metrics
- **user-story-generator**: Creates user stories counted in summary metrics
- **data-dictionary-generator**: Creates data dictionaries counted in summary
- **table-validation**: Creates validation reports counted in summary

Use `repo-summary-generator` **after** all other documentation skills to provide comprehensive portfolio metrics.
