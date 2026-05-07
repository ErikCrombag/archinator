"""Compaction tests."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend", "src"))

import pytest
from archinator.models import ArchiMateModel, Element, Relationship, CompactionMode
from archinator.compaction.compact import compact_model
from archinator.validation.validator import validate


def _elem(id, type, layer, aspect):
    return Element(id=id, type=type, name=id, layer=layer, aspect=aspect)


def _rel(id, type, src, tgt):
    return Relationship(id=id, type=type, source_id=src, target_id=tgt)


def _model(*elements, relationships=None):
    return ArchiMateModel(
        id="test", name="Test",
        elements=list(elements),
        relationships=list(relationships or []),
    )


def test_viewpoint_compact_removes_off_viewpoint_elements():
    m = _model(
        _elem("e1", "BusinessProcess", "Business", "Behavior"),
        _elem("e2", "Node", "Technology", "ActiveStructure"),
    )
    compacted = compact_model(m, CompactionMode.VIEWPOINT, viewpoint="BusinessProcess")
    types = {e.type for e in compacted.elements}
    assert "BusinessProcess" in types
    assert "Node" not in types


def test_viewpoint_compact_removes_off_viewpoint_relationships():
    e1 = _elem("e1", "BusinessProcess", "Business", "Behavior")
    e2 = _elem("e2", "BusinessFunction", "Business", "Behavior")
    e3 = _elem("e3", "Node", "Technology", "ActiveStructure")
    r1 = _rel("r1", "Triggering", "e1", "e2")
    r2 = _rel("r2", "Association", "e1", "e3")
    m = _model(e1, e2, e3, relationships=[r1, r2])
    compacted = compact_model(m, CompactionMode.VIEWPOINT, viewpoint="BusinessProcess")
    rel_ids = {r.id for r in compacted.relationships}
    # r2 removed because e3 (Node) is not in BusinessProcess viewpoint
    assert "r2" not in rel_ids


def test_full_compaction_preserves_everything():
    e1 = _elem("e1", "BusinessProcess", "Business", "Behavior")
    e2 = _elem("e2", "Node", "Technology", "ActiveStructure")
    r1 = _rel("r1", "Association", "e1", "e2")
    m = _model(e1, e2, relationships=[r1])
    compacted = compact_model(m, CompactionMode.FULL)
    assert len(compacted.elements) == 2
    assert len(compacted.relationships) == 1


def test_compacted_model_is_still_valid():
    e1 = _elem("e1", "BusinessProcess", "Business", "Behavior")
    e2 = _elem("e2", "BusinessFunction", "Business", "Behavior")
    e3 = _elem("e3", "Node", "Technology", "ActiveStructure")
    r1 = _rel("r1", "Triggering", "e1", "e2")
    r2 = _rel("r2", "Association", "e1", "e3")
    m = _model(e1, e2, e3, relationships=[r1, r2])
    compacted = compact_model(m, CompactionMode.VIEWPOINT, viewpoint="BusinessProcess")
    result = validate(compacted)
    assert result.valid


def test_no_dangling_relationships_after_compaction():
    e1 = _elem("e1", "BusinessProcess", "Business", "Behavior")
    e2 = _elem("e2", "Node", "Technology", "ActiveStructure")
    r1 = _rel("r1", "Association", "e1", "e2")
    m = _model(e1, e2, relationships=[r1])
    compacted = compact_model(m, CompactionMode.VIEWPOINT, viewpoint="BusinessProcess")
    elem_ids = {e.id for e in compacted.elements}
    for r in compacted.relationships:
        assert r.source_id in elem_ids, f"Dangling source: {r.source_id}"
        assert r.target_id in elem_ids, f"Dangling target: {r.target_id}"
