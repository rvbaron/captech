> **⚠️ SUPERSEDED — historical design notes, do not implement from this.**
> Original AST-extraction notes from branch `feature/hybrid-code-search` (last updated 2026-03-23). Superseded by the shipped extractor profiles under [`tools/legacylift_search/src/legacylift_search/profiles/extractors.json`](../../../../tools/legacylift_search/src/legacylift_search/profiles/extractors.json) and `extractors.py`. Retained for historical reference only — see [`README.md`](./README.md) in this folder.

Below are the **AST node kinds** I’d extract to build (a) a **caller→callee graph** and (b) robust **symbol identifiers** for your hybrid search layer, for your top 6 languages.

I’m listing **(1) call sites** and **(2) identifier/name nodes** (including “qualified/dotted” names) because those are the two anchors you need for: call graph, “unreferenced” analysis, and trace-forward/backward.

---

## 1) C# (tree-sitter-c-sharp)

### Call / invoke nodes to capture

* `invocation_expression` (method/function invocation) ([GitHub][1])
* `object_creation_expression` (`new Foo(...)`) ([GitHub][1])

### Identifier/name nodes to capture (callee resolution)

* `member_access_expression` (e.g., `obj.Method`) ([GitHub][1])
* `identifier` (leaf name) ([GitHub][1])
* Also useful for “what is being called”: `qualified_name`, `generic_name` (appear in the grammar around identifiers) ([GitHub][1])

**Practical extraction rule**

* For `invocation_expression`, extract:

  * **callee** from its “expression-ish” child: either `identifier` or `member_access_expression`
  * **arguments** for optional enrichment (for disambiguation / overload hints)

---

## 2) Java (tree-sitter-java)

### Call / invoke nodes to capture

* `method_invocation` ([GitHub][2])
* `object_creation_expression` (`new Foo(...)`) ([GitHub][2])
* (Optional but valuable) `method_reference` (e.g., `Type::method`) appears adjacent to method invocation in primary expressions ([GitHub][2])

### Identifier/name nodes to capture

* `identifier` ([GitHub][2])
* `field_access` (e.g., `obj.field`—also shows up in the same primary-expression cluster as method calls) ([GitHub][2])
* `scoped_identifier` (for qualified names; shows up as a type option next to `identifier`) ([GitHub][2])

**Practical extraction rule**

* For `method_invocation`, extract:

  * **method name** (`identifier`)
  * **target** from its receiver-ish expression when present (often `field_access` / other primary expressions)

---

## 3) Python (tree-sitter-python)

### Call / invoke nodes to capture

* `call` (function/method call) ([GitHub][3])

### Identifier/name nodes to capture

* `identifier` ([GitHub][3])
* `attribute` (e.g., `obj.method` where `attribute` has `object` + `attribute: identifier`) ([GitHub][3])
* For module-level dependency edges (nice for traversal/roots):

  * `import_statement`
  * `import_from_statement` ([GitHub][3])

**Practical extraction rule**

* For `call`, extract:

  * **callee**: either `identifier` or `attribute`
  * If `attribute`, extract `(object, attribute)` so you can later resolve imports/types heuristically.

---

## 4) JavaScript (tree-sitter-javascript)

### Call / invoke nodes to capture

* `call_expression` ([GitHub][4])

### Identifier/name nodes to capture

* `identifier` ([GitHub][4])
* `member_expression` (receiver + property) ([GitHub][4])
* `private_property_identifier` (class private fields/method-like access; shows up in expressions) ([GitHub][4])

**Practical extraction rule**

* For `call_expression`, extract callee from its `function` field (commonly `identifier` or `member_expression`) ([GitHub][4])
* Treat `subscript_expression` calls (computed props) separately if you want (e.g., `obj[fn]()`), but you can start with the three node kinds above.

---

## 5) TypeScript / TSX (tree-sitter-typescript)

### Call / invoke nodes to capture

* `call_expression` ([GitHub][5])

### Identifier/name nodes to capture

* `identifier` ([GitHub][5])
* `member_expression` ([GitHub][5])
* `property_identifier` (important for dot-property names in TS grammars) ([GitHub][5])
* `type_identifier` (helps tie call sites to types/interfaces/classes for better graph “jumps”) ([GitHub][5])

**Practical extraction rule**

* For `member_expression`, capture:

  * receiver expression
  * property node (`property_identifier` / `identifier`) so you can normalize to `Receiver.Property`.

---

## 6) COBOL (tree-sitter-cobol variants)

COBOL is the tricky one because:

* Dialects differ (Enterprise COBOL vs GnuCOBOL vs “partial” parsers)
* Some grammars model “identifiers” as generic `WORD` tokens and represent control-flow edges via **PERFORM/SECTION/PARAGRAPH** structures.

From the COBOL grammar you referenced (COBOL85-oriented), you *do* have:

* `qualified_word` (a good “name-like” symbol to store) ([GitHub][6])
* `WORD` (generic identifier token used widely) ([GitHub][6])
* Procedure structure keywords like `PARAGRAPH`, `PERFORM`, `PROCEDURE`, `PROGRAM` appear as named nodes/tokens ([GitHub][7])

### “Call graph” edges to start with (best effort)

Because CALL wasn’t discoverable in the portions we could reliably search, I’d start with *internal flow* edges first:

* **PERFORM → paragraph/section** as your “call”

  * Capture `PERFORM`
  * Capture the target as `qualified_word` / `WORD` following it (parser-specific, but usually present in the subtree) ([GitHub][7])
* **Paragraph declarations** (as callable nodes)

  * Capture `PARAGRAPH`-scoped blocks (and store their “name” as the `WORD`/`qualified_word` near the header) ([GitHub][7])

### Identifier/name nodes to capture

* `qualified_word`
* `WORD` ([GitHub][6])

**Recommendation (important)**

* Don’t hardcode COBOL node kinds across all clients.

  * Keep a COBOL “adapter” per grammar/dialect (IBM Enterprise COBOL grammar vs COBOL85 grammar differ a lot).
  * Use a *capability probe* at index-build time: “does this grammar expose a `call_statement`/`call` node?” If yes, use it. If not, fall back to PERFORM-graph.

---

## SQL (tree-sitter-sql)

SQL is also grammar-sensitive (ANSI-ish vs dialect-specific). The Derek Stride grammar exposes parser artifacts including `/src/node-types.json`. ([derekstride][8])

### What I’d extract (practical “top set”)

Even if the exact node names vary slightly by SQL grammar, your graph needs:

* **Routine invocations**

  * function calls (e.g., `function_call`)
  * procedure calls (e.g., `call_statement`)
* **Statement roots**

  * SELECT / INSERT / UPDATE / DELETE / MERGE / CREATE PROCEDURE / CREATE FUNCTION, etc.

### Identifier/name nodes

* object identifiers (tables/views)
* column identifiers
* schema-qualified names

**Recommendation (important)**

* SQL is where I would **not** hardcode node names at all.
* Instead, load the grammar’s `node-types.json` (Tree-sitter generates it ([Tree-sitter][9])) and maintain a small mapping config:

  * `call_nodes: [...]`
  * `identifier_nodes: [...]`
  * `statement_roots: [...]`

This gives you portability across:

* `tree-sitter-sql` vs `tree-sitter-postgres` vs `tree-sitter-sqlite`, etc.

---

# A robust way to implement this (so you don’t fight node-name drift)

For each language, define a **Language Extractor Profile**:

* `call_site_nodes`: list of node kinds to treat as “invokes”
* `callee_shapes`: patterns for extracting callee names from each call node (identifier vs member access vs attribute, etc.)
* `name_nodes`: leaf node kinds that represent an identifier
* `qualifier_nodes`: dotted/qualified structures (member access, scoped identifiers, qualified_word, etc.)

That profile can live in your `language-extractor.json`, and you can ship updates without changing code.

* See `language-extractor.json` for specific identifier/call AST node kinds to extract for the top 6 languages (C#, Java, Python, JS/TS, COBOL, SQL).


If you want, I can give you a **concrete per-language extractor profile** (JSON) matching the design you’re building (Chonkie + Chroma + graph-in-sqlite).

## Language Extraction
To get new languages, tell the coding agent the language/dialect (and ideally the tree-sitter parser repo name you’re using, or a small code snippet), and it will produce a new extractor block in the same JSON shape and tuned to:
- call site nodes (invocations / constructors / procedural calls)
- identifier + qualified-name nodes
- imports/include nodes (where applicable)
- symbol definition nodes (functions/classes/modules, etc.)
- dialect notes + fallbacks for drift between grammars

### Fast path (usually enough)
“Add extractor for Go” (or “PL/SQL”, “T-SQL”, “Ruby”, “Kotlin”, “PHP”, etc.)

### Best path (avoids node-name mismatch)
“Add extractor for SQL Server T-SQL using tree-sitter-tsql”

or

“Add extractor for COBOL (IBM Enterprise) using <parser link>”


[1]: https://github.com/tree-sitter/tree-sitter-c-sharp/blob/master/src/node-types.json "tree-sitter-c-sharp/src/node-types.json at master · tree-sitter/tree-sitter-c-sharp · GitHub"
[2]: https://github.com/tree-sitter/tree-sitter-java/blob/master/src/node-types.json "tree-sitter-java/src/node-types.json at master · tree-sitter/tree-sitter-java · GitHub"
[3]: https://github.com/tree-sitter/tree-sitter-python/blob/master/src/node-types.json "tree-sitter-python/src/node-types.json at master · tree-sitter/tree-sitter-python · GitHub"
[4]: https://github.com/tree-sitter/tree-sitter-javascript/blob/master/src/node-types.json "tree-sitter-javascript/src/node-types.json at master · tree-sitter/tree-sitter-javascript · GitHub"
[5]: https://github.com/tree-sitter/tree-sitter-typescript/blob/master/tsx/src/node-types.json "tree-sitter-typescript/tsx/src/node-types.json at master · tree-sitter/tree-sitter-typescript · GitHub"
[6]: https://github.com/yutaro-sakamoto/tree-sitter-cobol/blob/main/src/grammar.json "tree-sitter-cobol/src/grammar.json at main · yutaro-sakamoto/tree-sitter-cobol · GitHub"
[7]: https://github.com/yutaro-sakamoto/tree-sitter-cobol/blob/main/src/node-types.json "tree-sitter-cobol/src/node-types.json at main · yutaro-sakamoto/tree-sitter-cobol · GitHub"
[8]: https://derek.stride.host/tree-sitter-sql/ "tree-sitter-sql"
[9]: https://tree-sitter.github.io/tree-sitter/using-parsers/6-static-node-types?utm_source=chatgpt.com "Static Node Types"
