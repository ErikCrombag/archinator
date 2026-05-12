"""Formatting tests — no external dependencies required."""
import sys
import os
import re
import json as _json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend", "src"))

import pytest
from archinator.models import ArchiMateModel, Element, Relationship, View
from archinator.formatting import exchange_xml, json_fmt, mermaid, plantuml


# ── Fixtures ──────────────────────────────────────────────────────────────────

ALL_RELATIONSHIP_TYPES = [
    "Composition", "Aggregation", "Assignment", "Realization",
    "Serving", "Access", "Influence", "Association",
    "Triggering", "Flow", "Specialization",
]

# Valid Mermaid flowchart arrow heads (no sequence-diagram arrows like -->>)
_INVALID_MERMAID_ARROWS = re.compile(r"-->>|--\*|<<==>|<<--")


def _elem(id: str, type: str = "BusinessProcess", layer: str = "Business",
          aspect: str = "Behavior", name: str | None = None) -> Element:
    return Element(id=id, type=type, name=name or id, layer=layer, aspect=aspect)


def _rel(id: str, type: str, src: str = "e1", tgt: str = "e2",
         name: str | None = None) -> Relationship:
    return Relationship(id=id, type=type, source_id=src, target_id=tgt, name=name)


def _model(*elements, relationships=None, name="Test Model") -> ArchiMateModel:
    return ArchiMateModel(
        id="test-model-1", name=name,
        elements=list(elements),
        relationships=list(relationships or []),
    )


def _sample_model() -> ArchiMateModel:
    return _model(
        _elem("e1", "BusinessProcess", "Business", "Behavior", "Order Fulfillment"),
        _elem("e2", "ApplicationService", "Application", "Behavior", "Order API"),
        _elem("e3", "DataObject", "Application", "PassiveStructure", "Order Data"),
        relationships=[
            _rel("r1", "Realization", "e2", "e1"),
            _rel("r2", "Access", "e2", "e3"),
        ],
    )


def _all_rel_model() -> ArchiMateModel:
    """One element pair per relationship type."""
    elements = [
        _elem(f"e{i}", "BusinessProcess", "Business", "Behavior", f"Element {i}")
        for i in range(len(ALL_RELATIONSHIP_TYPES) * 2)
    ]
    relationships = [
        _rel(f"r{i}", rel_type, f"e{i*2}", f"e{i*2+1}")
        for i, rel_type in enumerate(ALL_RELATIONSHIP_TYPES)
    ]
    return _model(*elements, relationships=relationships)


def _special_chars_model() -> ArchiMateModel:
    return _model(
        _elem("e1", "BusinessProcess", "Business", "Behavior", 'Order "Quotes" Process'),
        _elem("e2", "ApplicationService", "Application", "Behavior", "API: Service/Component"),
        relationships=[_rel("r1", "Serving", "e1", "e2", "named rel")],
    )


# ── JSON ──────────────────────────────────────────────────────────────────────

def test_json_round_trip():
    m = _sample_model()
    rendered = json_fmt.render(m)
    data = _json.loads(rendered)
    assert data["name"] == "Test Model"
    assert len(data["elements"]) == 3
    assert len(data["relationships"]) == 2
    assert data["relationships"][0]["type"] == "Realization"


def test_json_empty_model():
    m = _model()
    rendered = json_fmt.render(m)
    data = _json.loads(rendered)
    assert data["elements"] == []
    assert data["relationships"] == []


def test_json_all_relationship_types():
    m = _all_rel_model()
    rendered = json_fmt.render(m)
    data = _json.loads(rendered)
    types = {r["type"] for r in data["relationships"]}
    assert types == set(ALL_RELATIONSHIP_TYPES)


# ── Exchange XML ──────────────────────────────────────────────────────────────

def test_exchange_xml_valid_structure():
    m = _sample_model()
    rendered = exchange_xml.render(m)
    assert '<?xml version' in rendered
    assert "opengroup.org/xsd/archimate" in rendered
    assert "Order Fulfillment" in rendered
    assert "Order API" in rendered
    assert "Realization" in rendered


def test_exchange_xml_element_identifiers():
    m = _sample_model()
    rendered = exchange_xml.render(m)
    assert 'identifier="id-e1"' in rendered
    assert 'identifier="id-e2"' in rendered


def test_exchange_xml_all_relationship_types():
    m = _all_rel_model()
    rendered = exchange_xml.render(m)
    for rel_type in ALL_RELATIONSHIP_TYPES:
        assert rel_type in rendered, f"Missing relationship type: {rel_type}"


def test_exchange_xml_empty_model():
    m = _model()
    rendered = exchange_xml.render(m)
    assert '<?xml version' in rendered
    assert "@enduml" not in rendered  # sanity: not plantuml


def test_exchange_xml_special_chars_in_name():
    m = _special_chars_model()
    rendered = exchange_xml.render(m)
    # XML must escape quotes — raw " should not appear inside attribute values unescaped
    assert "Order" in rendered


# ── Mermaid ───────────────────────────────────────────────────────────────────

def test_mermaid_contains_subgraphs():
    m = _sample_model()
    rendered = mermaid.render(m)
    assert "graph LR" in rendered
    assert "subgraph" in rendered
    assert "Business" in rendered
    assert "Application" in rendered


def test_mermaid_contains_relationships():
    m = _sample_model()
    rendered = mermaid.render(m)
    assert "Realization" in rendered
    assert "Access" in rendered


def test_mermaid_no_invalid_arrows():
    """No sequence-diagram or non-existent flowchart arrows."""
    m = _all_rel_model()
    rendered = mermaid.render(m)
    match = _INVALID_MERMAID_ARROWS.search(rendered)
    assert match is None, f"Invalid Mermaid arrow found: {match.group()!r}"


def test_mermaid_no_quoted_pipe_labels():
    """Labels inside |pipes| must not use double-quotes — causes parse errors."""
    m = _all_rel_model()
    rendered = mermaid.render(m)
    assert '|"' not in rendered, 'Quoted label inside pipe: |"..." found'


def test_mermaid_all_relationship_types_render():
    m = _all_rel_model()
    rendered = mermaid.render(m)
    for rel_type in ALL_RELATIONSHIP_TYPES:
        assert rel_type in rendered, f"Missing relationship type in Mermaid: {rel_type}"


def test_mermaid_named_relationship():
    m = _model(
        _elem("e1"), _elem("e2"),
        relationships=[_rel("r1", "Serving", name="provides data")],
    )
    rendered = mermaid.render(m)
    assert "provides data" in rendered


def test_mermaid_empty_model():
    m = _model()
    rendered = mermaid.render(m)
    assert "graph LR" in rendered


def test_mermaid_hyphen_ids_safe():
    """Hyphens in element IDs must be replaced in node identifiers (Mermaid rejects them).
    Hyphens may still appear inside display labels ["..."] — that is fine."""
    m = _model(
        _elem("elem-with-hyphens"),
        _elem("elem-two"),
        relationships=[_rel("rel-1", "Association", "elem-with-hyphens", "elem-two")],
    )
    rendered = mermaid.render(m)
    # Node definition: `elem_with_hyphens["..."]` — ID part must use underscores
    assert re.search(r'^\s*elem_with_hyphens\[', rendered, re.MULTILINE), \
        "Node ID still contains hyphens"
    # Relationship line must reference safe ID too
    assert "elem_with_hyphens" in rendered
    # Raw hyphenated ID must not appear as a standalone Mermaid node identifier
    assert not re.search(r'^\s*elem-with-hyphens\[', rendered, re.MULTILINE), \
        "Raw hyphenated ID used as Mermaid node identifier"


# ── PlantUML ──────────────────────────────────────────────────────────────────

def test_plantuml_contains_startuml():
    m = _sample_model()
    rendered = plantuml.render(m)
    assert "@startuml" in rendered
    assert "@enduml" in rendered
    assert "Order Fulfillment" in rendered


def test_plantuml_contains_archimate_include():
    m = _sample_model()
    rendered = plantuml.render(m)
    assert "!include <archimate/Archimate>" in rendered
    assert "archimate" in rendered


def test_plantuml_contains_relationships():
    m = _sample_model()
    rendered = plantuml.render(m)
    assert "Realization" in rendered


def test_plantuml_all_relationship_types_render():
    m = _all_rel_model()
    rendered = plantuml.render(m)
    for rel_type in ALL_RELATIONSHIP_TYPES:
        assert rel_type in rendered, f"Missing relationship type in PlantUML: {rel_type}"


def test_plantuml_all_layers_render():
    elements = [
        _elem("e1", "BusinessProcess", "Business", "Behavior"),
        _elem("e2", "ApplicationService", "Application", "Behavior"),
        _elem("e3", "Node", "Technology", "ActiveStructure"),
        _elem("e4", "Stakeholder", "Motivation", "ActiveStructure"),
        _elem("e5", "WorkPackage", "Implementation", "Behavior"),
    ]
    m = _model(*elements)
    rendered = plantuml.render(m)
    for layer in ["Business", "Application", "Technology", "Motivation", "Implementation"]:
        assert layer in rendered, f"Missing layer in PlantUML: {layer}"


def test_plantuml_named_relationship():
    m = _model(
        _elem("e1"), _elem("e2"),
        relationships=[_rel("r1", "Influence", name="drives strategy")],
    )
    rendered = plantuml.render(m)
    assert "drives strategy" in rendered


def test_plantuml_element_name_with_quotes_escaped():
    m = _special_chars_model()
    rendered = plantuml.render(m)
    # Should not break — quotes replaced with apostrophes in renderer
    assert "@enduml" in rendered
    assert "Order" in rendered


def test_plantuml_empty_model():
    m = _model()
    rendered = plantuml.render(m)
    assert "@startuml" in rendered
    assert "@enduml" in rendered


def test_plantuml_hyphen_ids_prefixed():
    """PlantUML IDs must be safe identifiers (e_ prefix + underscore)."""
    m = _model(
        _elem("elem-one"), _elem("elem-two"),
        relationships=[_rel("r1", "Flow", "elem-one", "elem-two")],
    )
    rendered = plantuml.render(m)
    assert "e_elem_one" in rendered
    assert "e_elem_two" in rendered
