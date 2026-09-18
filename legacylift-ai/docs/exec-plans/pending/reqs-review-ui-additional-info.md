# Overview

This document contains additional details for [reqs-review-ui.md](reqs-review-ui.md)

# Site Hierarchy
- Home (Dashboard): list of all projects
    - Project Detail
        - Content
            - Overview info
            - Current step in the process
            - Links to relevant pages (see bullets below)
        - Graph
        - Assess skill outputs
        - Map skill outputs
        - Requirements 
            - Landing page is datatable of all requirements, search
            - Requirements detail page
                - Show the requirements extracted - all fields
                - Editable fields for SME approve, SME justification, other "notes" types of fields
                - Links to code can show code viewer with syntax highlighting
        - Data (data objects MD file?)
        - Recommendation 
            - The outputs from the briefing skill
    - Knowledge
        - Requirement formats (the 10 types) description

# Implementation Notes
- Create a new platform-ui folder to hold all of this
- For now make a copy of the NNG requirements outputs to use (e.g., the various outputs and requirements)
- Can be read-only to start: demo is Wednesday so it needs to be displayable by then, I do not need edits by then.
- Any mermaid diagrams need to render - e.g., the fragments need to be included in the appropriate place
- Technology
    - API: C# / .NET latest RTS version
    - Front-end: Angular latest version
    - Data: use file stores or a copy of the Sqlite
        - Settings/the list of projects can be in a JSON file for now, again, read-only demo version
- Some UI colors and a logo are in the main branch, ./web/frontend folder
- Do NOT use Docker, I want this runnable from VS Code
- I understand that connecting to Sqlite is not the best, but it needs to work enough for the demo. In the future we will make it so a developer can upload outputs/output diffs to a central store.