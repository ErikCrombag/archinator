"""Formatting tests — no external dependencies required."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend", "src"))

import pytest
from archinator.models import ArchiMateModel, Element, Relationship, View
from archinator.formatting import exchange_xml, json_fmt, mermaid, plantuml


def _sample_model() -> ArchiMateModel:
    return ArchiMateModel(
        id="test-model-1",
        name="Test Model",
        elements=[
            Element(id="e1", type="BusinessProcess", name="Order Fulfillment",
                    layer="Business", aspect="Behavior"),
            Element(id="e2", type="ApplicationService", name="Order API",
                    layer="Application", aspect="Behavior"),
            Element(id="e3", type="DataObject", name="Order Data",
                    layer="Application", aspect="PassiveStructure"),
        ],
        relationships=[
            Relationship(id="r1", type="Realization", source_id="e2", target_id="e1"),
            Relationship(id="r2", type="Access", source_id="e2", target_id="e3",
                         access_type="ReadWrite"),
        ],
        views=[
            View(id="v1", name="Application Usage", viewpoint="ApplicationUsage",
                 element_ids=["e1", "e2", "e3"], relationship_ids=["r1", "r2"]),
        ],
    )


def test_json_round_trip():
    m = _sample_model()
    rendered = json_fmt.render(m)
    import json
    data = json.loads(rendered)
    assert data["name"] == "Test Model"
    assert len(data["elements"]) == 3
    assert len(data["relationships"]) == 2
    assert data["relationships"][0]["type"] == "Realization"


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


def test_plantuml_contains_startuml():
    m = _sample_model()
    rendered = plantuml.render(m)
    assert "@startuml" in rendered
    assert "@enduml" in rendered
    assert "Order Fulfillment" in rendered


def test_plantuml_contains_relationships():
    m = _sample_model()
    rendered = plantuml.render(m)
    assert "Realization" in rendered
