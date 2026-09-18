"""Framework-aware XML symbol/reference extractor.

Unlike the tree-sitter / regex ``SymbolExtractor`` in ``extractors.py``, this
module understands the *semantics* of the XML dialects that carry real
architectural meaning in legacy Java/Spring estates:

- **Hibernate mapping** (``*.hbm.xml``, root ``<hibernate-mapping>``): each
  ``<class name="…" table="…">`` yields a mapping symbol plus a ``uses_table``
  reference (hbm → DB table) and a ``maps_to`` reference (hbm → the mapped Java
  entity class). ``<property>``/``<column>`` yield field→column references and
  ``<many-to-one>``/``<one-to-many>`` yield entity association references. This
  reconstructs the DAO→entity→table data-lineage the plain call graph cannot
  see.
- **Spring WebFlow** (root ``<flow>``): the flow is an entry point; each
  ``<view-state>``/``<action-state>``/``<decision-state>``/``<end-state>``/
  ``<subflow-state>`` is a state symbol; ``<evaluate expression="bean.method()">``
  yields a reference to the invoked Java method (flow → Java), ``<transition>``
  yields an intra-flow ``transitions_to`` reference, and ``<subflow-state>``
  yields a subflow invocation.
- **Spring beans** (root ``<beans>``): each ``<bean id="…" class="…">`` yields a
  bean symbol plus an ``instantiates`` reference to its Java class.
- **Anything else**: a single file-level symbol so the file remains searchable
  and coverable, with no spurious edges.

References resolve against the repo-wide symbol name index by the existing
``GraphBuilder``; unresolved targets (e.g. a table with no indexed DDL) are
preserved as low-confidence edges exactly like any other unresolved reference.

Line numbers come from ``xml.parsers.expat`` (``CurrentLineNumber`` /
``CurrentByteIndex``), which is stable across CPython versions — the
ElementTree line-number recipes are not.
"""

from __future__ import annotations

import re
import xml.parsers.expat
from typing import Any

from .models import ExtractedFile, Symbol, SymbolRef, TextRange


# Root element -> dialect.
_ROOT_HIBERNATE = "hibernate-mapping"
_ROOT_FLOW = "flow"
_ROOT_BEANS = "beans"

# Leading identifier chain of a WebFlow evaluate expression, e.g.
# "definitionAction.init(definitionStateHolder)" -> ("definitionAction", "init").
# We take the first bean token and the first method-call token after it.
_EVAL_CALL_RE = re.compile(
    r"([A-Za-z_$][\w$]*)\s*\.\s*([A-Za-z_$][\w$]*)\s*\("
)


def _simple_name(qualified: str) -> str:
    """Return the last dot-segment of a possibly fully-qualified name."""
    q = (qualified or "").strip()
    if not q:
        return q
    return q.rsplit(".", 1)[-1]


class _Element:
    """A parsed XML element with source position and parent link."""

    __slots__ = ("tag", "attrs", "start_line", "start_byte", "end_line", "parent")

    def __init__(
        self, tag: str, attrs: dict, start_line: int, start_byte: int, parent: "_Element | None"
    ) -> None:
        self.tag = tag
        self.attrs = attrs
        self.start_line = start_line
        self.start_byte = start_byte
        self.end_line = start_line
        self.parent = parent


def _parse_elements(text: str) -> list[_Element]:
    """Parse XML into a flat, source-ordered element list with line numbers.

    Raises ``xml.parsers.expat.ExpatError`` on malformed input.
    """
    parser = xml.parsers.expat.ParserCreate()
    elements: list[_Element] = []
    stack: list[_Element] = []

    def start(tag: str, attrs: dict) -> None:
        el = _Element(
            tag=tag,
            attrs=attrs,
            start_line=parser.CurrentLineNumber,
            start_byte=parser.CurrentByteIndex,
            parent=stack[-1] if stack else None,
        )
        elements.append(el)
        stack.append(el)

    def end(_tag: str) -> None:
        if stack:
            el = stack.pop()
            el.end_line = parser.CurrentLineNumber

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.Parse(text.encode("utf-8", errors="replace"), True)
    return elements


def _enclosing(el: _Element, tags: set[str]) -> _Element | None:
    """Walk the parent chain to the nearest ancestor whose tag is in ``tags``."""
    cur = el.parent
    while cur is not None:
        if cur.tag in tags:
            return cur
        cur = cur.parent
    return None


class _Emitter:
    """Accumulates symbols/refs with correctly-formatted ids for one file."""

    def __init__(self, language: str, relative_path: str) -> None:
        self.language = language
        self.relative_path = relative_path
        self.symbols: list[Symbol] = []
        self.refs: list[SymbolRef] = []

    def _range(self, el: _Element) -> TextRange:
        return TextRange(
            start_byte=max(el.start_byte, 0),
            end_byte=max(el.start_byte, 0),
            start_line=max(el.start_line, 1),
            end_line=max(el.end_line, el.start_line, 1),
        )

    def symbol(
        self, el: _Element, name: str, qualified: str, kind: str, entity_class: str
    ) -> str:
        """Emit one symbol.

        `entity_class` is required, not defaulted, on this call: every caller
        below already knows its dialect's semantics (a Hibernate `<property>`
        is a `field`, a WebFlow state is `other`) and must say so at the point
        of emission (§S3.1.2) — there is no `entity_class_of(kind)` to fall
        back on, and there must never be one. An unclassified kind is `other`,
        and promoting a kind out of `other` later is an `ak2:` event: it
        re-keys every `anchor_key` derived from it, across both databases.
        """
        rng = self._range(el)
        sym_id = f"{self.language}:{self.relative_path}:{qualified}:{rng.start_line}"
        container = qualified.rsplit(".", 1)[0] if "." in qualified else None
        self.symbols.append(
            Symbol(
                id=sym_id,
                language=self.language,
                name=name,
                qualified_name=qualified,
                kind=kind,
                range=rng,
                container=container,
                signature=None,
                entity_class=entity_class,
            )
        )
        return sym_id

    def ref(
        self, el: _Element, name: str, kind: str, evidence: str, enclosing_id: str | None
    ) -> None:
        if not name:
            return
        rng = self._range(el)
        ref_id = (
            f"{self.language}:{self.relative_path}:ref:{name}:"
            f"{rng.start_line}:{rng.start_byte}:{kind}"
        )
        self.refs.append(
            SymbolRef(
                id=ref_id,
                language=self.language,
                name=name,
                kind=kind,
                range=rng,
                enclosing_symbol_id=enclosing_id,
                evidence=evidence[:200],
            )
        )


def _extract_hibernate(em: _Emitter, elements: list[_Element]) -> None:
    class_tags = {"class", "subclass", "joined-subclass", "union-subclass"}
    class_ids: dict[int, str] = {}  # id(element) -> symbol id, for enclosing lookup

    for el in elements:
        tag = el.tag
        if tag in class_tags:
            fq = (el.attrs.get("name") or el.attrs.get("entity-name") or "").strip()
            simple = _simple_name(fq) or "<anonymous-class>"
            sym_id = em.symbol(
                el, simple, fq or simple, "hibernate_class_mapping", "type"
            )
            class_ids[id(el)] = sym_id
            # hbm -> Java entity class (resolves to the mapped @Entity/class).
            if fq:
                em.ref(el, simple, "hibernate_entity", f'class name="{fq}"', sym_id)
            table = (el.attrs.get("table") or "").strip()
            if table:
                em.ref(el, table, "hibernate_table", f'table="{table}"', sym_id)
        elif tag in ("property", "id", "version", "timestamp"):
            enclosing = _enclosing(el, class_tags)
            enclosing_id = class_ids.get(id(enclosing)) if enclosing else None
            pname = (el.attrs.get("name") or "").strip()
            if pname and enclosing is not None:
                cls_fq = (
                    enclosing.attrs.get("name")
                    or enclosing.attrs.get("entity-name")
                    or ""
                ).strip()
                cls_simple = _simple_name(cls_fq) or "<class>"
                # The extractor already knows a Hibernate <property>/<id>/
                # <version>/<timestamp> child is state, so it declares
                # `field` here rather than emitting `hibernate_{tag}` and
                # leaving something downstream to infer it from the string.
                em.symbol(
                    el, pname, f"{cls_simple}.{pname}", f"hibernate_{tag}", "field"
                )
            # column mapping (may be an attribute on the property or a child).
            col = (el.attrs.get("column") or "").strip()
            if col:
                em.ref(el, col, "hibernate_column", f'column="{col}"', enclosing_id)
        elif tag == "column":
            enclosing = _enclosing(el, class_tags)
            enclosing_id = class_ids.get(id(enclosing)) if enclosing else None
            col = (el.attrs.get("name") or "").strip()
            if col:
                em.ref(el, col, "hibernate_column", f'column name="{col}"', enclosing_id)
        elif tag in ("many-to-one", "one-to-many", "many-to-many", "one-to-one"):
            enclosing = _enclosing(el, class_tags)
            enclosing_id = class_ids.get(id(enclosing)) if enclosing else None
            target_fq = (el.attrs.get("class") or "").strip()
            if target_fq:
                em.ref(
                    el,
                    _simple_name(target_fq),
                    "hibernate_association",
                    f'{tag} class="{target_fq}"',
                    enclosing_id,
                )


def _extract_webflow(em: _Emitter, elements: list[_Element], flow_name: str) -> None:
    state_tags = {
        "view-state",
        "action-state",
        "decision-state",
        "end-state",
        "subflow-state",
    }
    root = elements[0] if elements else None
    flow_id = None
    if root is not None:
        # A flow and its states are process/config, not code entities in the
        # closed six; §S3.1.2 puts every WebFlow state, the flow itself, and
        # `xml_document` in `other`.
        flow_id = em.symbol(root, flow_name, flow_name, "webflow_flow", "other")

    state_ids: dict[int, str] = {}
    for el in elements:
        if el.tag in state_tags:
            sid = (el.attrs.get("id") or "").strip() or "<state>"
            state_sym = em.symbol(
                el, sid, f"{flow_name}.{sid}", el.tag.replace("-", "_"), "other"
            )
            state_ids[id(el)] = state_sym
            if el.tag == "subflow-state":
                sub = (el.attrs.get("subflow") or "").strip()
                if sub:
                    em.ref(el, sub, "webflow_subflow", f'subflow="{sub}"', state_sym)

    for el in elements:
        enclosing_state = _enclosing(el, state_tags)
        enc_id = state_ids.get(id(enclosing_state)) if enclosing_state else flow_id
        if el.tag == "evaluate":
            expr = (el.attrs.get("expression") or "").strip()
            m = _EVAL_CALL_RE.search(expr)
            if m:
                # Reference the invoked method (resolves to a Java method symbol).
                em.ref(el, m.group(2), "webflow_evaluate", expr, enc_id)
        elif el.tag == "transition":
            to = (el.attrs.get("to") or "").strip()
            if to:
                em.ref(el, to, "webflow_transition", f'transition to="{to}"', enc_id)


def _extract_spring_beans(em: _Emitter, elements: list[_Element]) -> None:
    for el in elements:
        if el.tag == "bean":
            bean_id = (el.attrs.get("id") or el.attrs.get("name") or "").strip()
            cls = (el.attrs.get("class") or "").strip()
            label = bean_id or _simple_name(cls) or "<bean>"
            sym_id = em.symbol(el, label, bean_id or label, "spring_bean", "type")
            if cls:
                em.ref(
                    el, _simple_name(cls), "spring_bean_class", f'class="{cls}"', sym_id
                )


def extract_xml(
    language: str, relative_path: str, text: str, file_stem: str
) -> ExtractedFile:
    """Extract framework-aware symbols/refs from an XML document.

    Args:
        language: language key (always ``"xml"`` here).
        relative_path: repo-relative POSIX path (used in symbol/ref ids).
        text: full file text.
        file_stem: filename without extensions (used as the WebFlow flow name).

    Returns:
        ExtractedFile. On malformed XML, returns empty symbols/refs plus a
        parse error; the file still gets line-window chunks downstream and thus
        stays searchable.
    """
    try:
        elements = _parse_elements(text)
    except xml.parsers.expat.ExpatError as exc:
        return ExtractedFile(
            symbols=[], refs=[], parse_errors=[f"xml parse error: {exc}"]
        )
    except Exception as exc:  # pragma: no cover - defensive
        return ExtractedFile(
            symbols=[], refs=[], parse_errors=[f"xml extract failed: {exc!r}"]
        )

    if not elements:
        return ExtractedFile(symbols=[], refs=[], parse_errors=[])

    em = _Emitter(language, relative_path)
    root_tag = elements[0].tag

    if root_tag == _ROOT_HIBERNATE:
        _extract_hibernate(em, elements)
    elif root_tag == _ROOT_FLOW:
        _extract_webflow(em, elements, file_stem)
    elif root_tag == _ROOT_BEANS:
        _extract_spring_beans(em, elements)
    else:
        # Unknown dialect: one file-level symbol so it stays searchable, no
        # edges. `other`, not `file` — `file` is reserved for the identity
        # module's own file-grain anchor (`file_anchor_key`), which this
        # symbol is not.
        em.symbol(
            elements[0],
            file_stem or root_tag,
            file_stem or root_tag,
            "xml_document",
            "other",
        )

    return ExtractedFile(symbols=em.symbols, refs=em.refs, parse_errors=[])


__all__ = ["extract_xml"]
