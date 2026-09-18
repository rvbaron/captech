> ⚠️ **PROPRIETARY – HIGHLY SENSITIVE** ⚠️

> LegacyLift is CapTech intellectual property.
> This repository is not open source and may only be accessed and used by authorized CapTech personnel or clients under a specific Statement of Work.

---

# LegacyLift Classic: AI-driven Requirements Reverse Engineering

**LegacyLift Classic** (v3.7.0) is the Claude Code plugin that packages the LegacyLift documentation suite — 18 skills that analyze legacy codebases and generate high-quality, enterprise-grade documentation to accelerate modernization projects.

The per-skill reference — inventory, execution order, and pipeline — is [`skills/README.md`](./skills/README.md).

## Install

**Copy this folder from the LegacyLift repo.** There is no marketplace entry; the plugin is
proprietary and ships only from this repository.

Copy the whole directory into the project you want to document, at exactly this path:

```bash
# from the root of the repository you will run the skills against
mkdir -p .claude/skills
cp -r /path/to/legacylift-ai/.claude/skills/legacylift-classic .claude/skills/
```

The skills then resolve under the `legacylift-classic:` namespace — as slash commands
(`/legacylift-classic:fact-graph`) or on the CLI
(`claude --skill legacylift-classic:exec-summary-generator .`). Nothing from LegacyLift v4 is
needed: no index, no data store, no `legacylift-search`.

## Features

- **Automated Documentation Generation:**
  - Analyze legacy codebases and generate comprehensive documentation.
  - Create executive summaries, system architecture, data models, business rules, and integration guides.
- **Claude Skills Integration:**
  - Powered by Claude Code skills that systematically analyze code structure, architecture, and business logic.
  - Multiple specialized skills for different documentation needs (`exec-summary-generator`, `business-documenter`, `data-documenter`, `si-documenter`, `use-case-generator`, `user-story-generator`, etc.).
- **Professional Quality Output:**
  - Industry-standard documentation with inline source code citations.
  - Mermaid diagrams for visualizations (C4 diagrams, ERDs, sequence diagrams).
  - Progressive disclosure structure targeting multiple audiences.
- **Codebase-Aware:**
  - Deep code analysis with precise file paths and line number citations.

## Skill Names

Every skill in this plugin is addressed with the `legacylift-classic:` prefix — as a slash command (`/legacylift-classic:exec-summary-generator`) or on the CLI (`claude --skill legacylift-classic:exec-summary-generator .`). The bare names (`/exec-summary-generator`) worked before v3.7.0, when these skills lived directly under `.claude/skills/`; they no longer resolve.

## How It Works

1. **Run Claude Skills:**
   ```bash
   cd ./repos/your-repository
   claude --skill legacylift-classic:exec-summary-generator .
   # Or use other specific skills:
   # claude --skill legacylift-classic:business-documenter .
   # claude --skill legacylift-classic:data-documenter .
   # claude --skill legacylift-classic:si-documenter .
   ```

2. **Systematic 7-Phase Analysis:**
   - Initial discovery (project structure, technology stack)
   - Architecture analysis (design patterns, service boundaries)
   - Data model extraction (entities, relationships, schemas)
   - Business logic analysis (rules, workflows, validations)
   - API & integration mapping (endpoints, auth, external services)
   - Document generation (writing with inline citations)
   - Review & polish (quality assurance)

3. **Output Generation:**
   - Creates professional markdown documentation in the `legacylift-docs/` folder of the target repository
   - Inline source code citations with file paths and line numbers
   - Mermaid diagrams for visual representations
   - Cross-references between related documents

## Tech Stack

- **AI Engine:** Claude Code skills with Claude Sonnet / Opus
- **Documentation Tools:** Multi-phase analysis, code search (Glob/Grep), template system, diagram generation

## Requirements

- Claude Code CLI (for skills execution)
- Python 3.12 (for any auxiliary scripts)

## File Structure

- `.claude-plugin/plugin.json` — plugin manifest (name, version, description)
- `skills/` — the 18 skill definitions, one directory per skill
- `skills/README.md` — skills inventory, execution order, and pipeline reference
- `skills/FACT-GRAPH-INTEGRATION.md` — canonical Phase 0 specification shared by every fact-graph-backed skill
- `skills/STATUS-REPORTING.md` — canonical progress-reporting specification shared across skills

## Example Use Case

Generate comprehensive documentation for a legacy application:

```bash
cd ./repos/ctcm/ctcm-api
claude --skill legacylift-classic:exec-summary-generator .
claude --skill legacylift-classic:business-documenter .
claude --skill legacylift-classic:data-documenter .
claude --skill legacylift-classic:si-documenter .
```

Documentation is generated in the repository's `legacylift-docs/` folder:
- `00-EXECUTIVE-SUMMARY.md`
- `01-SYSTEM-ARCHITECTURE.md`
- `02-DATA-MODEL-AND-RELATIONSHIPS.md`
- `03-BUSINESS-RULES-AND-REQUIREMENTS.md`
- `04-INTEGRATION-AND-API-GUIDE.md`
- `05-QUICK-REFERENCE.md`
- Additional specialized documents (use cases, user stories, validation reports, etc.)

---
*Empower your legacy modernization with AI-driven clarity and speed.*
