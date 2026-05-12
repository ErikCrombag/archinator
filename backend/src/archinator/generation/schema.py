"""
Build the Ollama JSON schema for ArchiMate model generation.

Passing a schema (not just format="json") constrains the model at the token
level — it cannot emit invalid element types, wrong layers, or missing fields.
This is the highest-leverage improvement for model output quality.
"""
from __future__ import annotations
from ..validation.rules import ELEMENT_TYPES, RELATIONSHIP_TYPES

_ELEMENT_ENUM = sorted(ELEMENT_TYPES.keys())
_RELATIONSHIP_ENUM = sorted(RELATIONSHIP_TYPES)
_LAYER_ENUM = sorted({v["layer"] for v in ELEMENT_TYPES.values()})
_ASPECT_ENUM = sorted({v["aspect"] for v in ELEMENT_TYPES.values()})


def build_ollama_schema() -> dict:
    """Return a JSON Schema dict for the ArchiMateModel response."""
    return {
        "type": "object",
        "required": ["id", "name", "elements", "relationships", "views"],
        "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "elements": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id", "type", "name", "layer", "aspect"],
                    "properties": {
                        "id":          {"type": "string"},
                        "type":        {"type": "string", "enum": _ELEMENT_ENUM},
                        "name":        {"type": "string"},
                        "layer":       {"type": "string", "enum": _LAYER_ENUM},
                        "aspect":      {"type": "string", "enum": _ASPECT_ENUM},
                        "description": {"type": ["string", "null"]},
                        "properties":  {"type": "object"},
                    },
                },
            },
            "relationships": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id", "type", "source_id", "target_id"],
                    "properties": {
                        "id":                 {"type": "string"},
                        "type":               {"type": "string", "enum": _RELATIONSHIP_ENUM},
                        "source_id":          {"type": "string"},
                        "target_id":          {"type": "string"},
                        "name":               {"type": ["string", "null"]},
                        "access_type":        {"enum": ["Read", "Write", "ReadWrite", None]},
                        "influence_modifier": {"type": ["string", "null"]},
                        "properties":         {"type": "object"},
                    },
                },
            },
            "views": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id", "name"],
                    "properties": {
                        "id":               {"type": "string"},
                        "name":             {"type": "string"},
                        "viewpoint":        {"type": ["string", "null"]},
                        "element_ids":      {"type": "array", "items": {"type": "string"}},
                        "relationship_ids": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
        },
    }
