"""Caller/callee graph construction.

Milestone 8 (Agent C1): Build graph edges from extracted symbols and references.
Each edge represents a call/reference relationship with a confidence score that
reflects the resolver's certainty. Unresolved references are preserved as edges
with null callee_symbol_id to enable later refinement.

See ``docs/exec-plans/active/semantic-code-search-graph-index.md``.
"""

from __future__ import annotations

import re
from typing import Mapping

from .models import GraphEdge, SourceFile, Symbol, SymbolRef


class GraphBuilder:
    """Build caller/callee graph edges from symbols and references.

    For each reference:
    1. Determine the caller symbol (prefer ref.enclosing_symbol_id, else find
       the nearest symbol whose range contains the ref line).
    2. Resolve the callee symbol against all known symbols by exact qualified
       name match, then by plain name.
    3. Assign confidence based on resolution quality:
       - 0.85: exactly one candidate found
       - 0.70: multiple candidates in same language, same-file preferred
       - 0.40: multiple candidates, cross-file/language ambiguity
       - 0.30: no candidate found (unresolved)
    4. Assign edge kind based on ref.kind and language context.
    """

    def build_edges(
        self,
        source_file: SourceFile,
        symbols: list[Symbol],
        refs: list[SymbolRef],
        all_symbols_by_name: Mapping[str, list[Symbol]],
    ) -> list[GraphEdge]:
        """Build graph edges for all references in a source file.

        Args:
            source_file: The file being processed.
            symbols: Symbols extracted from this file (used for caller/range lookup).
            refs: References extracted from this file.
            all_symbols_by_name: Index of all symbols across the entire repo,
                grouped by plain name for resolution.

        Returns:
            List of graph edges with confidence scores and evidence.
        """
        edges: list[GraphEdge] = []

        for ref in refs:
            # 1. Determine caller
            caller_id = self._resolve_caller(ref, symbols)

            # 2. Resolve callee (also carries the resolved target's kind, used
            #    to reclassify the ambiguous C# inherits_or_implements case)
            callee_id, confidence, callee_kind = self._resolve_callee(
                ref, all_symbols_by_name, source_file
            )

            # 3. Determine edge kind
            edge_kind = self._edge_kind_from_ref(
                ref, source_file.language, callee_kind
            )

            # 4. Build edge ID
            # Fold ``ref.id`` (unique per ref) into the edge id. Milestone 25:
            # multiple same-type refs on one line — ``void Save(Claim a,
            # Claim b)`` or ``Dictionary<Claim, Claim> map`` — share
            # name/start_line/edge_kind and would otherwise collapse to one
            # edge on upsert, silently undercounting. ``ref.id`` carries the
            # type node's start_byte, so it disambiguates them. This widening is
            # a no-op for M22/M23/M24 (no per-line duplicate refs there).
            caller_or_file = caller_id if caller_id else source_file.relative_path
            edge_id = (
                f"edge:{caller_or_file}:{ref.name}:{ref.range.start_line}:"
                f"{edge_kind}:{ref.id}"
            )

            # 5. Create edge
            edge = GraphEdge(
                id=edge_id,
                caller_symbol_id=caller_id,
                callee_symbol_id=callee_id,
                callee_name=ref.name,
                edge_kind=edge_kind,
                confidence=confidence,
                evidence=ref.evidence,
                source_ref_id=ref.id,
                relative_path=source_file.relative_path,
                start_line=ref.range.start_line,
            )
            edges.append(edge)

        return edges

    def _resolve_caller(
        self, ref: SymbolRef, symbols: list[Symbol]
    ) -> str | None:
        """Identify the caller symbol for a reference.

        Prefers ref.enclosing_symbol_id if present; otherwise finds the nearest
        symbol whose range contains the ref line.
        """
        if ref.enclosing_symbol_id:
            return ref.enclosing_symbol_id

        # Find nearest containing symbol
        ref_line = ref.range.start_line
        best: Symbol | None = None

        for sym in symbols:
            if sym.range.start_line <= ref_line <= sym.range.end_line:
                # Prefer the most specific (innermost) symbol
                if best is None or (
                    sym.range.start_line >= best.range.start_line
                    and sym.range.end_line <= best.range.end_line
                ):
                    best = sym

        return best.id if best else None

    def _resolve_callee(
        self,
        ref: SymbolRef,
        all_symbols_by_name: Mapping[str, list[Symbol]],
        source_file: SourceFile,
    ) -> tuple[str | None, float, str | None]:
        """Resolve the callee symbol and assign confidence.

        Returns:
            (callee_symbol_id, confidence, callee_kind) where confidence is:
            - 0.85: exactly one candidate
            - 0.70: multiple in same language, same-file preferred
            - 0.40: multiple candidates, ambiguous
            - 0.30: no candidate found

            ``callee_kind`` is the chosen Symbol's ``kind`` (e.g.
            ``interface_declaration``) or None when unresolved. Milestone 22
            threads it into ``_edge_kind_from_ref`` to reclassify C#
            ``inherits_or_implements`` bases; the callee-id string does not
            encode kind, and re-looking-up by name would be unsafe when several
            same-name candidates exist, so it must travel with the id.
        """
        # Try exact qualified name match first
        candidates = all_symbols_by_name.get(ref.name, [])

        if not candidates:
            # No matching symbol at all
            return None, 0.30, None

        if len(candidates) == 1:
            # Exactly one candidate - high confidence
            return candidates[0].id, 0.85, candidates[0].kind

        # Multiple candidates - prefer same language, then same file
        same_lang = [c for c in candidates if c.language == ref.language]

        if same_lang:
            # Prefer same-file candidate if available
            same_file_cands = [
                c for c in same_lang
                if self._same_file(c, source_file)
            ]
            if same_file_cands:
                return same_file_cands[0].id, 0.70, same_file_cands[0].kind
            # Same language but different file
            return same_lang[0].id, 0.70, same_lang[0].kind

        # Multiple candidates, cross-language ambiguity
        return None, 0.40, None

    def _same_file(self, symbol: Symbol, source_file: SourceFile) -> bool:
        """Check if a symbol's ID indicates it's from the same file."""
        # Symbol ID format: <language>:<relative-path>:<qualified-name>:<start-line>
        parts = symbol.id.split(":", 2)
        if len(parts) < 2:
            return False
        return parts[1] == source_file.relative_path

    def _edge_kind_from_ref(
        self, ref: SymbolRef, language: str, callee_kind: str | None = None
    ) -> str:
        """Determine edge kind from reference kind and language context.

        Maps tree-sitter/fallback ref.kind values to semantic edge kinds:
        - calls: generic method/function invocation
        - performs: COBOL PERFORM statement
        - executes_sql: COBOL EXEC SQL block
        - executes_cics: COBOL EXEC CICS block
        - uses_table: SQL table reference (FROM, JOIN, UPDATE, INTO)
        - imports: import/using directive
        - inherits / implements: Milestone 22 type-hierarchy edges
        - foreign_key / associates: Milestone 23 annotation-driven relational edges
        - has_field_of_type / accepts_dto / returns_dto: Milestone 25 type-ref edges
        - references: generic reference

        ``callee_kind`` (Milestone 22) is the resolved target Symbol's kind, or
        None if unresolved; used only to reclassify C#
        ``inherits_or_implements`` bases.
        """
        ref_kind = ref.kind.lower()

        # Milestone 22: type-hierarchy edges. Test the ambiguous C# case with
        # exact equality (NOT substring membership: "implements" is a substring
        # of "inherits_or_implements", so an `in` test would mislabel every C#
        # base as implements and defeat the reclassification below).
        if ref_kind == "inherits_or_implements":
            # C# base_list: reclassify from the resolved target's kind when
            # known; when the base is external/unresolved (callee_kind is None),
            # fall back to the .NET interface-naming heuristic rather than
            # defaulting to inherits — in a real .NET app the majority of
            # base-list entries are external framework interfaces.
            if callee_kind == "interface_declaration":
                return "implements"
            if callee_kind is not None:
                return "inherits"
            return "implements" if re.match(r"^I[A-Z]", ref.name) else "inherits"
        if ref_kind == "implements":
            return "implements"
        if ref_kind == "extends":
            return "inherits"

        # Milestone 23: annotation-driven relational edges. These come from the
        # SymbolExtractor annotation handler (@JoinColumn/@ManyToOne etc.) with
        # an explicit kind. They MUST have their own branches here — without
        # them the final `return "references"` fallthrough would silently
        # relabel them `references`, so the edge count would rise as expected
        # while the typed foreign_key/associates deliverable went missing.
        if ref_kind == "foreign_key":
            return "foreign_key"
        if ref_kind == "associates":
            return "associates"

        # Milestone 25: field/property type references and method signature
        # types. Each new ref kind MUST have an explicit branch here — without
        # it the final `return "references"` fallthrough would silently relabel
        # them `references`, so the edge count would rise as expected while the
        # typed has_field_of_type / accepts_dto / returns_dto deliverable went
        # missing (the silent-default hazard the plan warns about).
        if ref_kind == "has_field_of_type":
            return "has_field_of_type"
        if ref_kind == "accepts_dto":
            return "accepts_dto"
        if ref_kind == "returns_dto":
            return "returns_dto"

        # XML framework mappings (Hibernate / Spring WebFlow / Spring beans).
        # These come from the dedicated xml_extractor and carry explicit kinds.
        if language == "xml":
            xml_edge = {
                "hibernate_table": "uses_table",
                "hibernate_column": "uses_column",
                "hibernate_entity": "maps_to",
                "hibernate_association": "associates",
                "spring_bean_class": "instantiates",
                "webflow_evaluate": "calls",
                "webflow_subflow": "invokes_subflow",
                "webflow_transition": "transitions_to",
            }.get(ref_kind)
            if xml_edge:
                return xml_edge
            return "references"

        # COBOL-specific mappings
        if language == "cobol":
            # Check evidence first for COBOL keywords (covers fallback_call cases)
            evidence = ref.evidence.upper()
            if "EXEC SQL" in evidence:
                return "executes_sql"
            if "EXEC CICS" in evidence:
                return "executes_cics"
            if "PERFORM" in evidence or "perform" in ref_kind:
                return "performs"
            if "CALL" in evidence:
                return "calls"
            # Tree-sitter specific nodes
            if "exec" in ref_kind and "sql" in ref_kind:
                return "executes_sql"
            if "exec" in ref_kind and "cics" in ref_kind:
                return "executes_cics"
            if "call" in ref_kind:
                return "calls"

        # SQL-specific mappings
        if language == "sql":
            if "exec" in ref_kind or "call" in ref_kind:
                return "calls"
            # Table references
            evidence = ref.evidence.upper()
            if any(kw in evidence for kw in ["FROM", "JOIN", "UPDATE", "INTO"]):
                return "uses_table"
            # Fallback for SQL object references
            if "table_reference" in ref_kind or "object_reference" in ref_kind:
                return "uses_table"

        # Import/using directives
        if "import" in ref_kind or "using" in ref_kind:
            return "imports"

        # Generic call patterns
        if any(kw in ref_kind for kw in [
            "call", "invocation", "method_invocation", "object_creation"
        ]):
            return "calls"

        # Default fallback
        return "references"


__all__ = ["GraphBuilder"]
