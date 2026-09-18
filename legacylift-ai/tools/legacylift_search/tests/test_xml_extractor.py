"""Tests for the framework-aware XML extractor (Hibernate / WebFlow / Spring)
and its integration with SymbolExtractor dispatch, GraphBuilder edge kinds, and
language registration.
"""

from __future__ import annotations

from pathlib import Path

from legacylift_search.extractors import SymbolExtractor, load_profiles
from legacylift_search.graph import GraphBuilder
from legacylift_search.languages import detect_language
from legacylift_search.models import SourceFile
from legacylift_search.xml_extractor import extract_xml


PACKAGE_ROOT = Path(__file__).parent.parent / "src" / "legacylift_search"
PROFILE_PATH = PACKAGE_ROOT / "profiles" / "extractors.json"


HIBERNATE_HBM = """<?xml version="1.0"?>
<hibernate-mapping default-lazy="false">
    <class name="com.nng.ple.model.Lesaddress" table="LES_ADDRESS">
        <id name="systemAssignedKey" type="java.lang.Integer">
            <column name="ADDRESS_ID" precision="9" />
            <generator class="native" />
        </id>
        <property name="street" type="string">
            <column name="STREET_NAME" length="40" />
        </property>
        <many-to-one name="legalEntity" class="com.nng.ple.model.LesLegalEntity">
            <column name="LEGAL_ENTITY_ID" />
        </many-to-one>
    </class>
</hibernate-mapping>
"""

WEBFLOW_XML = """<?xml version="1.0" encoding="UTF-8"?>
<flow xmlns="http://www.springframework.org/schema/webflow">
    <on-start>
        <evaluate expression="definitionAction.init(stateHolder)" result="flowScope.sh"/>
    </on-start>
    <view-state id="definitionMaintenance" view="singlepane.layout">
        <transition on="lookup" to="results">
            <evaluate expression="definitionAction.lookup(flowScope.sh)"/>
        </transition>
    </view-state>
    <subflow-state id="editSub" subflow="legalEntityGroup">
        <transition on="done" to="definitionMaintenance"/>
    </subflow-state>
    <end-state id="results"/>
</flow>
"""

SPRING_BEANS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<beans xmlns="http://www.springframework.org/schema/beans">
    <bean id="definitionAction" class="com.nng.ple.web.actions.DefinitionAction"/>
    <bean id="dateService" class="com.nng.arch.datesplit.DateRangeService"/>
</beans>
"""

UNKNOWN_XML = """<?xml version="1.0"?>
<web-app><servlet><servlet-name>ple</servlet-name></servlet></web-app>
"""

MALFORMED_XML = "<hibernate-mapping><class name='Foo' table='BAR'>"  # never closed


def _rel(name: str) -> str:
    return f"ple-persistence/{name}"


# --- language registration -------------------------------------------------


def test_xml_extension_registered():
    spec = detect_language(Path("Foo.hbm.xml"))
    assert spec is not None
    assert spec.key == "xml"
    # plain .xml too
    assert detect_language(Path("beans.xml")).key == "xml"


# --- Hibernate -------------------------------------------------------------


def test_hibernate_class_table_entity():
    ef = extract_xml("xml", _rel("Lesaddress.hbm.xml"), HIBERNATE_HBM, "Lesaddress")
    assert ef.parse_errors == []
    # class mapping symbol present with fully-qualified name
    cls = [s for s in ef.symbols if s.kind == "hibernate_class_mapping"]
    assert len(cls) == 1
    assert cls[0].qualified_name == "com.nng.ple.model.Lesaddress"
    assert cls[0].name == "Lesaddress"
    assert cls[0].entity_class == "type"
    # <property>/<id> children declare entity_class="field" at emission
    # (§S3.1.2) -- they are state, the COBOL/JS analogue of a field.
    props = [s for s in ef.symbols if s.kind in ("hibernate_property", "hibernate_id")]
    assert props and all(s.entity_class == "field" for s in props)
    # table ref
    tables = [r.name for r in ef.refs if r.kind == "hibernate_table"]
    assert tables == ["LES_ADDRESS"]
    # entity ref (hbm -> Java class)
    entities = [r.name for r in ef.refs if r.kind == "hibernate_entity"]
    assert entities == ["Lesaddress"]
    # association ref to the related entity
    assocs = [r.name for r in ef.refs if r.kind == "hibernate_association"]
    assert "LesLegalEntity" in assocs
    # column refs captured
    cols = [r.name for r in ef.refs if r.kind == "hibernate_column"]
    assert "STREET_NAME" in cols and "ADDRESS_ID" in cols


def test_hibernate_line_numbers_are_sane():
    ef = extract_xml("xml", _rel("Lesaddress.hbm.xml"), HIBERNATE_HBM, "Lesaddress")
    cls = [s for s in ef.symbols if s.kind == "hibernate_class_mapping"][0]
    # <class> is on line 3 of the fixture (1=xml decl, 2=hibernate-mapping)
    assert cls.range.start_line == 3
    assert cls.range.end_line >= cls.range.start_line


# --- WebFlow ---------------------------------------------------------------


def test_webflow_states_and_evaluates():
    ef = extract_xml("xml", "ple-web/flows/definition.xml", WEBFLOW_XML, "definition")
    assert ef.parse_errors == []
    kinds = {s.kind for s in ef.symbols}
    assert "webflow_flow" in kinds
    assert "view_state" in kinds
    assert "subflow_state" in kinds
    assert "end_state" in kinds
    # every WebFlow state and the flow itself declare entity_class="other"
    # (§S3.1.2): process/config, not a code entity in the closed six.
    assert all(s.entity_class == "other" for s in ef.symbols)
    # evaluate -> Java method
    evals = [r.name for r in ef.refs if r.kind == "webflow_evaluate"]
    assert "init" in evals and "lookup" in evals
    # transition target
    trans = [r.name for r in ef.refs if r.kind == "webflow_transition"]
    assert "results" in trans
    # subflow invocation
    subs = [r.name for r in ef.refs if r.kind == "webflow_subflow"]
    assert "legalEntityGroup" in subs


# --- Spring beans ----------------------------------------------------------


def test_spring_beans():
    ef = extract_xml("xml", "ple-web/beans.xml", SPRING_BEANS_XML, "beans")
    beans = [s for s in ef.symbols if s.kind == "spring_bean"]
    assert {b.name for b in beans} == {"definitionAction", "dateService"}
    assert all(b.entity_class == "type" for b in beans)
    classes = [r.name for r in ef.refs if r.kind == "spring_bean_class"]
    assert "DefinitionAction" in classes and "DateRangeService" in classes


# --- unknown + malformed ---------------------------------------------------


def test_unknown_dialect_yields_one_searchable_symbol_no_edges():
    ef = extract_xml("xml", "ple-web/web.xml", UNKNOWN_XML, "web")
    assert ef.parse_errors == []
    assert len(ef.symbols) == 1
    assert ef.symbols[0].kind == "xml_document"
    assert ef.symbols[0].entity_class == "other"
    assert ef.refs == []


def test_malformed_xml_degrades_gracefully():
    ef = extract_xml("xml", _rel("broken.hbm.xml"), MALFORMED_XML, "broken")
    assert ef.symbols == []
    assert ef.refs == []
    assert ef.parse_errors and "xml parse error" in ef.parse_errors[0]


# A whole .hbm.xml mapping wrapped in a single XML comment (a developer
# disabled it). extract_xml returns a parse error (0 symbols); the real repo
# case (DunsSetup.hbm.xml) previously hung the CHUNKER because XML with no
# symbols fell through to Chonkie's language="auto", which infinite-looped.
COMMENTED_OUT_HBM = (
    "<!-- <?xml version='1.0'?>\n"
    "<hibernate-mapping schema='edi'>\n"
    "    <class name='com.nng.Foo' table='FOO'>\n"
    "        <id name='id'><column name='ID'/></id>\n"
    "    </class>\n"
    "</hibernate-mapping>\n"
    " -->"
)


def test_commented_out_hbm_yields_parse_error_not_hang():
    ef = extract_xml("xml", _rel("DunsSetup.hbm.xml"), COMMENTED_OUT_HBM, "DunsSetup")
    assert ef.symbols == []
    assert ef.parse_errors  # expat: "no element found"


def test_chunker_skips_chonkie_for_xml_and_never_hangs():
    """Regression: a symbol-less XML file must chunk via the deterministic
    line-based fallback, NOT Chonkie's auto-detect (which hung on the
    comment-wrapped DunsSetup.hbm.xml). Guards the build-stall bug."""
    from legacylift_search.chunking import CodeChunker
    from legacylift_search.config import ChunkingConfig
    from legacylift_search.models import ExtractedFile

    sf = SourceFile(
        absolute_path=Path("DunsSetup.hbm.xml").resolve(),
        repo_root=Path(".").resolve(),
        relative_path=_rel("DunsSetup.hbm.xml"),
        language="xml",
        size_bytes=len(COMMENTED_OUT_HBM.encode("utf-8")),
        sha256="0" * 64,
        mtime_ns=0,
    )
    empty = ExtractedFile(symbols=[], refs=[], parse_errors=["xml parse error"])
    chunks = CodeChunker(ChunkingConfig()).chunk(sf, COMMENTED_OUT_HBM, empty)
    assert chunks  # produced something
    assert all(c.chunk_kind != "chonkie" for c in chunks)


# --- SymbolExtractor dispatch ----------------------------------------------


def test_symbol_extractor_dispatches_xml():
    profiles = load_profiles(PROFILE_PATH)
    extractor = SymbolExtractor(profiles)
    sf = SourceFile(
        absolute_path=Path("Lesaddress.hbm.xml").resolve(),
        repo_root=Path(".").resolve(),
        relative_path=_rel("Lesaddress.hbm.xml"),
        language="xml",
        size_bytes=len(HIBERNATE_HBM.encode("utf-8")),
        sha256="0" * 64,
        mtime_ns=0,
    )
    ef = extractor.extract(sf, HIBERNATE_HBM)
    assert any(s.kind == "hibernate_class_mapping" for s in ef.symbols)
    assert any(r.kind == "hibernate_table" for r in ef.refs)


def test_compound_extension_stem_for_flow_name():
    """A *.hbm.xml file's flow-name stem strips both extensions."""
    profiles = load_profiles(PROFILE_PATH)
    extractor = SymbolExtractor(profiles)
    sf = SourceFile(
        absolute_path=Path("home.xml").resolve(),
        repo_root=Path(".").resolve(),
        relative_path="ple-web/flows/home.xml",
        language="xml",
        size_bytes=len(WEBFLOW_XML.encode("utf-8")),
        sha256="0" * 64,
        mtime_ns=0,
    )
    ef = extractor.extract(sf, WEBFLOW_XML)
    flow = [s for s in ef.symbols if s.kind == "webflow_flow"][0]
    assert flow.name == "home"


# --- GraphBuilder edge kinds -----------------------------------------------


def test_graph_edge_kinds_for_xml():
    ef = extract_xml("xml", _rel("Lesaddress.hbm.xml"), HIBERNATE_HBM, "Lesaddress")
    sf = SourceFile(
        absolute_path=Path("Lesaddress.hbm.xml").resolve(),
        repo_root=Path(".").resolve(),
        relative_path=_rel("Lesaddress.hbm.xml"),
        language="xml",
        size_bytes=1,
        sha256="0" * 64,
        mtime_ns=0,
    )
    builder = GraphBuilder()
    edges = builder.build_edges(sf, ef.symbols, ef.refs, {})
    kinds = {e.edge_kind for e in edges}
    assert "uses_table" in kinds
    assert "maps_to" in kinds
    assert "associates" in kinds
    # unresolved table (no DDL indexed) still becomes a preserved edge
    table_edges = [e for e in edges if e.edge_kind == "uses_table"]
    assert table_edges and table_edges[0].callee_name == "LES_ADDRESS"


def test_maps_to_resolves_against_java_entity():
    """A hibernate_entity ref resolves to the mapped Java class symbol when it
    exists in the repo-wide name index (this is the DAO->entity->table bridge)."""
    from legacylift_search.models import Symbol, TextRange

    java_entity = Symbol(
        id="java:ple-model/.../Lesaddress.java:Lesaddress:10",
        language="java",
        name="Lesaddress",
        qualified_name="com.nng.ple.model.Lesaddress",
        kind="class_declaration",
        range=TextRange(start_byte=0, end_byte=1, start_line=10, end_line=200),
        entity_class="type",
    )
    ef = extract_xml("xml", _rel("Lesaddress.hbm.xml"), HIBERNATE_HBM, "Lesaddress")
    sf = SourceFile(
        absolute_path=Path("Lesaddress.hbm.xml").resolve(),
        repo_root=Path(".").resolve(),
        relative_path=_rel("Lesaddress.hbm.xml"),
        language="xml",
        size_bytes=1,
        sha256="0" * 64,
        mtime_ns=0,
    )
    builder = GraphBuilder()
    edges = builder.build_edges(
        sf, ef.symbols, ef.refs, {"Lesaddress": [java_entity]}
    )
    maps_to = [e for e in edges if e.edge_kind == "maps_to"]
    assert maps_to
    # resolved to the Java entity symbol id with high confidence
    assert maps_to[0].callee_symbol_id == java_entity.id
    assert maps_to[0].confidence >= 0.85
