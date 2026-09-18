# legacylift-search: framework-aware XML extractor (Hibernate / WebFlow / Spring)

_Added 2026-07-01 to support the NNG PLE comparison (Hibernate `.hbm.xml` data-lineage) and, going forward, any Java/Spring estate. Tool change under `tools/legacylift_search/`._

## Why

The index originally covered only code languages (`.java`, `.cs`, `.py`, `.js`, `.ts`, COBOL, `.sql`). Legacy Java/Spring estates carry real architecture in XML:
- **Hibernate `.hbm.xml`** — the Java-entity ↔ DB-table mapping (the DAO→entity→table data lineage). The NNG app has 133 of these in `ple-persistence`.
- **Spring WebFlow flow XML** — entry points and screen/action state machines (33 flows).
- **Spring bean XML** — DI wiring, Quartz jobs (14 config files).

Adding `.xml` to include-globs alone does nothing: `discovery.py` drops any file whose extension isn't in the language registry (`languages.py`). And a generic XML parse would yield elements/attributes, not "this class maps to this table." So this is a real extractor, not a config flip.

## What changed (5 edits + 1 new module + tests)

1. **`languages.py`** — registered an `xml` language (extension `.xml`, `supports_tree_sitter=False`, like COBOL). Without this, discovery skips `.xml`.
2. **`xml_extractor.py`** (new) — a dedicated, stdlib-`expat` extractor (stable line numbers across CPython). Dispatches on root element:
   - `<hibernate-mapping>`: per `<class name=… table=…>` → a `hibernate_class_mapping` symbol + a `hibernate_entity` ref (→ Java class) + a `hibernate_table` ref (→ DB table); `<property>`/`<id>` → field symbols + `hibernate_column` refs; `<many-to-one>`/`<one-to-many>`/etc → `hibernate_association` refs (→ related entity).
   - `<flow>` (WebFlow): flow + per-state symbols (`view-state`/`action-state`/`decision-state`/`end-state`/`subflow-state`); `<evaluate expression="bean.method()">` → `webflow_evaluate` ref (→ Java method); `<transition to=…>` → `webflow_transition`; `<subflow-state subflow=…>` → `webflow_subflow`.
   - `<beans>` (Spring): per `<bean id=… class=…>` → `spring_bean` symbol + `spring_bean_class` ref (→ Java class).
   - anything else → one `xml_document` symbol so the file stays searchable/coverable, no spurious edges.
   - malformed XML → empty symbols/refs + a `parse_errors` entry; the file still gets line-window chunks downstream (searchable).
3. **`extractors.py`** — `SymbolExtractor.extract()` dispatches `language == "xml"` to `extract_xml()` before the tree-sitter/profile path (so both serial and parallel worker paths route XML). XML has no entry in `extractors.json` and needs none.
4. **`graph.py`** — new XML ref-kind → edge-kind map: `hibernate_table→uses_table`, `hibernate_column→uses_column`, `hibernate_entity→maps_to`, `hibernate_association→associates`, `spring_bean_class→instantiates`, `webflow_evaluate→calls`, `webflow_subflow→invokes_subflow`, `webflow_transition→transitions_to`. Refs resolve against the repo-wide symbol name index by the existing `GraphBuilder` — so a `maps_to` ref binds the hbm mapping to the actual Java `@Entity`/class symbol (high confidence), and an unresolved table (no DDL indexed) is preserved as a low-confidence edge exactly like any other unresolved reference.
5. **`config.py`** — default `include_globs` gained targeted XML patterns (NOT blanket `**/*.xml`, to avoid IDE/build noise): `**/*.hbm.xml`, `**/*-flow.xml`, `**/flows/**/*.xml`, `**/*.beans.xml`, `**/applicationContext*.xml`, `**/spring/**/*.xml`, `**/config/**/*.xml`. Default `exclude_globs` gained `**/.settings/**`, `**/build.xml`, `**/ivy.xml`, `**/pom.xml`.

**"Automatic in the future":** because the patterns are in `config.py`'s `Manifest` defaults, any repo indexed *without* a custom manifest picks up Hibernate/WebFlow/Spring XML automatically. Repos with their own `semantic-search.manifest.json` (like ctcm and this NNG repo) must add the patterns to that file — done for NNG; ctcm is C#/EF so it has no `.hbm.xml`.

## Tests

`tests/test_xml_extractor.py` (11 tests): language registration; Hibernate class/table/entity/column/association extraction + line numbers; WebFlow states/evaluates/transitions/subflow; Spring beans; unknown-dialect single-symbol; malformed-XML graceful degradation; `SymbolExtractor` dispatch; compound-extension stem; `GraphBuilder` XML edge kinds incl. the `maps_to`-resolves-to-Java-entity bridge. Full suite: **182 passed** (171 baseline + 11).

## Discovery preview (NNG app, updated manifest)

`discover_source_files` now returns 1,239 files: java 995, xml 183 (133 hbm + 33 flows + 17 config/bean), sql 50, javascript 11. **Zero** IDE/build noise leaked (`.settings`, `build.xml`, `bin/` all excluded).

## Caveat carried forward

The `maps_to` bridge resolves hbm→Java-entity when the entity class name is in the index (it is — `ple-model` is indexed). The `uses_table` edge target (the physical table) resolves only if DDL for that table is indexed; the NNG DDL lives in the *sibling* `customer.ple.nng.db.ETSPii` repo, not indexed here, so table edges are mostly preserved-unresolved (low confidence) — which is still the correct, useful representation (it names the table even without the DDL).
