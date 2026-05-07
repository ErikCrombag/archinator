"""Validation tests — no external dependencies required."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend", "src"))

import pytest
from archinator.models import Element, Relationship, ArchiMateModel
from archinator.validation.validator import validate


def _model(*elements, relationships=None):
    return ArchiMateModel(
        id="test", name="Test",
        elements=list(elements),
        relationships=list(relationships or []),
    )


def _elem(id, type, layer, aspect, name=None):
    return Element(id=id, type=type, name=name or id, layer=layer, aspect=aspect)


def _rel(id, type, source, target):
    return Relationship(id=id, type=type, source_id=source, target_id=target)


# ── Element type legality ─────────────────────────────────────────────────────

def test_valid_element_types_pass():
    m = _model(
        _elem("e1", "BusinessProcess", "Business", "Behavior"),
        _elem("e2", "ApplicationService", "Application", "Behavior"),
    )
    result = validate(m)
    assert result.valid


def test_invalid_element_type_caught():
    m = _model(_elem("e1", "MagicBox", "Business", "Behavior"))
    result = validate(m)
    assert not result.valid
    assert any(v.rule == "element_type_legality" for v in result.violations)


def test_wrong_layer_for_type_caught():
    m = _model(_elem("e1", "BusinessProcess", "Application", "Behavior"))
    result = validate(m)
    assert not result.valid
    assert any(v.rule == "layer_consistency" for v in result.violations)


def test_wrong_aspect_for_type_caught():
    m = _model(_elem("e1", "BusinessProcess", "Business", "PassiveStructure"))
    result = validate(m)
    assert not result.valid
    assert any(v.rule == "aspect_consistency" for v in result.violations)


# ── Relationship type legality ────────────────────────────────────────────────

def test_valid_relationship_type_pass():
    e1 = _elem("e1", "ApplicationComponent", "Application", "ActiveStructure")
    e2 = _elem("e2", "ApplicationService", "Application", "Behavior")
    r = _rel("r1", "Assignment", "e1", "e2")
    result = validate(_model(e1, e2, relationships=[r]))
    assert result.valid


def test_invalid_relationship_type_caught():
    e1 = _elem("e1", "BusinessProcess", "Business", "Behavior")
    e2 = _elem("e2", "BusinessActor", "Business", "ActiveStructure")
    r = _rel("r1", "MagicLink", "e1", "e2")
    result = validate(_model(e1, e2, relationships=[r]))
    assert not result.valid
    assert any(v.rule == "relationship_type_legality" for v in result.violations)


# ── Relationship endpoint validation ─────────────────────────────────────────

def test_dangling_relationship_caught():
    e1 = _elem("e1", "BusinessProcess", "Business", "Behavior")
    r = _rel("r1", "Association", "e1", "nonexistent")
    result = validate(_model(e1, relationships=[r]))
    assert not result.valid
    assert any(v.rule == "relationship_endpoint" for v in result.violations)


# ── Aspect rule validation ────────────────────────────────────────────────────

def test_access_behavior_to_passive_passes():
    e1 = _elem("e1", "ApplicationProcess", "Application", "Behavior")
    e2 = _elem("e2", "DataObject", "Application", "PassiveStructure")
    r = _rel("r1", "Access", "e1", "e2")
    result = validate(_model(e1, e2, relationships=[r]))
    assert result.valid


def test_access_passive_to_behavior_fails():
    e1 = _elem("e1", "DataObject", "Application", "PassiveStructure")
    e2 = _elem("e2", "ApplicationProcess", "Application", "Behavior")
    r = _rel("r1", "Access", "e1", "e2")
    result = validate(_model(e1, e2, relationships=[r]))
    assert not result.valid
    assert any(v.rule == "relationship_aspect_legality" for v in result.violations)


def test_triggering_between_behaviors_passes():
    e1 = _elem("e1", "BusinessProcess", "Business", "Behavior")
    e2 = _elem("e2", "BusinessFunction", "Business", "Behavior")
    r = _rel("r1", "Triggering", "e1", "e2")
    result = validate(_model(e1, e2, relationships=[r]))
    assert result.valid


def test_triggering_to_passive_fails():
    e1 = _elem("e1", "BusinessProcess", "Business", "Behavior")
    e2 = _elem("e2", "BusinessObject", "Business", "PassiveStructure")
    r = _rel("r1", "Triggering", "e1", "e2")
    result = validate(_model(e1, e2, relationships=[r]))
    assert not result.valid


# ── Viewpoint constraints ─────────────────────────────────────────────────────

def test_viewpoint_unknown_gives_warning():
    e1 = _elem("e1", "BusinessProcess", "Business", "Behavior")
    result = validate(_model(e1), viewpoint="NonexistentViewpoint")
    assert any(v.rule == "viewpoint_unknown" and v.severity == "warning" for v in result.violations)


def test_viewpoint_filters_invalid_element_as_warning():
    e1 = _elem("e1", "Node", "Technology", "ActiveStructure")
    result = validate(_model(e1), viewpoint="BusinessProcess")
    warnings = [v for v in result.violations if v.rule == "viewpoint_element"]
    assert warnings


def test_full_viewpoint_allows_everything():
    e1 = _elem("e1", "BusinessProcess", "Business", "Behavior")
    e2 = _elem("e2", "Node", "Technology", "ActiveStructure")
    r = _rel("r1", "Association", "e1", "e2")
    result = validate(_model(e1, e2, relationships=[r]), viewpoint="Full")
    assert result.valid
