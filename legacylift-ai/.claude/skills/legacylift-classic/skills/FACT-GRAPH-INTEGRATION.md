# Fact Graph Integration - Phase 0

This document provides the canonical Phase 0 fact-graph loading logic that should be used consistently across all skills that support fact-graph integration.

## When to Use This

Include Phase 0 in skills that:
- Analyze code structure (entities, services, controllers, etc.)
- Extract business logic or data models
- Map relationships and dependencies
- Need to avoid redundant code scanning

## Canonical Phase 0 Code

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

        # Only mark as loaded if we actually got data
        if len(entities) > 0:
            fact_graph_loaded = True
            print(f"\n✅ Loaded fact graph: {len(entities)} entities, {len(relations)} relations, {len(facts)} facts")
            if packs_metadata:
                print(f"   Domains: {len(packs_metadata)}")
                for pack in packs_metadata:
                    print(f"   - {pack['domain']}: {pack['entity_count']} entities, {pack['relation_count']} relations, {pack['fact_count']} facts")
        else:
            fact_graph_loaded = False
            print("⚠️ Fact graph index found but no pack data loaded")
            print("   Falling back to direct code analysis")
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

## Usage in Subsequent Phases

```python
if fact_graph_loaded:
    # Use fact graph data
    services = find_entities_by_type('service')
    controllers = find_entities_by_type('controller')

    # Access domain-specific entities
    core_entities = find_entities_by_domain('Core')

    # Query business rules
    business_rules = find_facts_by_predicate('business_rule')
else:
    # Fallback to direct code analysis using Task/Explore, Grep, Glob
    # ... original grep/glob commands ...
```

## Pack Format

The fact-graph skill generates **domain-scoped pack files**:
- `{domain}.entities.pack.json` - Entity definitions for a domain
- `{domain}.relations.pack.json` - Relationships between entities
- `{domain}.facts.pack.json` - Facts/attributes about entities

Example pack files:
- `core.entities.pack.json`
- `api.entities.pack.json`
- `points.entities.pack.json`

## Skills Using Phase 0

The following skills include Phase 0 fact-graph loading:

**Documentation Generators:**
- **si-documenter** - System architecture and integration documentation
- **business-documenter** - Business rules and requirements documentation
- **data-documenter** - Data model documentation
- **exec-summary-generator** - Executive summary generation
- **database-layer-documenter** - Database layer analysis
- **detailed-req-documenter** - Detailed requirements per capability
- **data-dictionary-generator** - Exhaustive database data dictionaries

**Requirements & Use Cases:**
- **use-case-generator** - Comprehensive use case documentation
- **user-story-generator** - User stories organized into epics

**Validation & Review:**
- **table-validation** - ORM mapping validation against DDL
- **gap-analyzer** - Documentation-code gap analysis
- **documentation-review** - Documentation accuracy verification
- **citation-validator** - Line number citation validation

## Maintaining Consistency

When updating Phase 0 logic:
1. Update this canonical reference (FACT-GRAPH-INTEGRATION.md)
2. Update all skills listed above to match
3. Ensure helper functions remain consistent
4. Test with both fact-graph present and absent scenarios
