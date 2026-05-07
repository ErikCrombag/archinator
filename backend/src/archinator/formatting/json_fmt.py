from __future__ import annotations
import json
import dataclasses
from ..models import ArchiMateModel


def render(model: ArchiMateModel) -> str:
    return json.dumps(_model_to_dict(model), indent=2, ensure_ascii=False)


def _model_to_dict(model: ArchiMateModel) -> dict:
    return {
        "id": model.id,
        "name": model.name,
        "metadata": model.metadata,
        "elements": [
            {
                "id": e.id,
                "type": e.type,
                "name": e.name,
                "layer": e.layer,
                "aspect": e.aspect,
                "description": e.description,
                "properties": e.properties,
            }
            for e in model.elements
        ],
        "relationships": [
            {
                "id": r.id,
                "type": r.type,
                "source_id": r.source_id,
                "target_id": r.target_id,
                "name": r.name,
                "access_type": r.access_type,
                "influence_modifier": r.influence_modifier,
                "properties": r.properties,
            }
            for r in model.relationships
        ],
        "views": [
            {
                "id": v.id,
                "name": v.name,
                "viewpoint": v.viewpoint,
                "element_ids": v.element_ids,
                "relationship_ids": v.relationship_ids,
            }
            for v in model.views
        ],
    }
