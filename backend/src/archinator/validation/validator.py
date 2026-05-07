from __future__ import annotations
from ..models import ArchiMateModel, ValidationResult, ValidationViolation
from .rules import (
    ANY, ELEMENT_TYPES, RELATIONSHIP_TYPES, RELATIONSHIP_RULES, VIEWPOINTS, LAYER_ORDER
)


def validate(model: ArchiMateModel, viewpoint: str | None = None) -> ValidationResult:
    violations: list[ValidationViolation] = []
    violations += _check_element_types(model)
    violations += _check_relationship_types(model)
    violations += _check_relationship_endpoints(model)
    violations += _check_relationship_aspect_rules(model)
    violations += _check_layer_consistency(model)
    if viewpoint:
        violations += _check_viewpoint_constraints(model, viewpoint)
    valid = all(v.severity != "error" for v in violations)
    return ValidationResult(valid=valid, violations=violations)


def _check_element_types(model: ArchiMateModel) -> list[ValidationViolation]:
    out = []
    for e in model.elements:
        if e.type not in ELEMENT_TYPES:
            out.append(ValidationViolation(
                rule="element_type_legality",
                message=f"Unknown element type '{e.type}' on element '{e.name}' ({e.id})",
                element_id=e.id,
                severity="error",
            ))
        else:
            spec = ELEMENT_TYPES[e.type]
            if e.layer != spec["layer"]:
                out.append(ValidationViolation(
                    rule="layer_consistency",
                    message=(
                        f"Element '{e.name}' ({e.id}) has layer '{e.layer}' "
                        f"but type '{e.type}' belongs to layer '{spec['layer']}'"
                    ),
                    element_id=e.id,
                    severity="error",
                ))
            if e.aspect != spec["aspect"]:
                out.append(ValidationViolation(
                    rule="aspect_consistency",
                    message=(
                        f"Element '{e.name}' ({e.id}) has aspect '{e.aspect}' "
                        f"but type '{e.type}' has aspect '{spec['aspect']}'"
                    ),
                    element_id=e.id,
                    severity="error",
                ))
    return out


def _check_relationship_types(model: ArchiMateModel) -> list[ValidationViolation]:
    out = []
    for r in model.relationships:
        if r.type not in RELATIONSHIP_TYPES:
            out.append(ValidationViolation(
                rule="relationship_type_legality",
                message=f"Unknown relationship type '{r.type}' ({r.id})",
                relationship_id=r.id,
                severity="error",
            ))
    return out


def _check_relationship_endpoints(model: ArchiMateModel) -> list[ValidationViolation]:
    element_ids = {e.id for e in model.elements}
    out = []
    for r in model.relationships:
        if r.source_id not in element_ids:
            out.append(ValidationViolation(
                rule="relationship_endpoint",
                message=f"Relationship '{r.id}' references unknown source element '{r.source_id}'",
                relationship_id=r.id,
                severity="error",
            ))
        if r.target_id not in element_ids:
            out.append(ValidationViolation(
                rule="relationship_endpoint",
                message=f"Relationship '{r.id}' references unknown target element '{r.target_id}'",
                relationship_id=r.id,
                severity="error",
            ))
    return out


def _check_relationship_aspect_rules(model: ArchiMateModel) -> list[ValidationViolation]:
    elem_map = {e.id: e for e in model.elements}
    out = []
    for r in model.relationships:
        if r.type not in RELATIONSHIP_RULES:
            continue
        src = elem_map.get(r.source_id)
        tgt = elem_map.get(r.target_id)
        if not src or not tgt:
            continue
        rule = RELATIONSHIP_RULES[r.type]
        if not _aspects_allowed(src.aspect, tgt.aspect, rule["allowed_pairs"]):
            out.append(ValidationViolation(
                rule="relationship_aspect_legality",
                message=(
                    f"Relationship '{r.type}' from '{src.name}' ({src.aspect}) "
                    f"to '{tgt.name}' ({tgt.aspect}) is not permitted by ArchiMate 3.2 rules"
                ),
                relationship_id=r.id,
                severity="error",
            ))
        if not rule.get("cross_layer", True) and src.layer != tgt.layer:
            out.append(ValidationViolation(
                rule="relationship_cross_layer",
                message=(
                    f"Relationship '{r.type}' ({r.id}) spans layers "
                    f"'{src.layer}' → '{tgt.layer}' but is restricted to same-layer"
                ),
                relationship_id=r.id,
                severity="error",
            ))
    return out


def _aspects_allowed(src_aspect: str, tgt_aspect: str, pairs: list[tuple[str, str]]) -> bool:
    for s, t in pairs:
        src_ok = s == ANY or s == src_aspect
        tgt_ok = t == ANY or t == tgt_aspect
        if src_ok and tgt_ok:
            return True
    return False


def _check_layer_consistency(model: ArchiMateModel) -> list[ValidationViolation]:
    elem_map = {e.id: e for e in model.elements}
    out = []
    for r in model.relationships:
        if r.type not in ("Realization", "Serving"):
            continue
        src = elem_map.get(r.source_id)
        tgt = elem_map.get(r.target_id)
        if not src or not tgt:
            continue
        src_order = LAYER_ORDER.get(src.layer, 99)
        tgt_order = LAYER_ORDER.get(tgt.layer, 99)
        if r.type == "Realization" and src_order > tgt_order:
            out.append(ValidationViolation(
                rule="realization_direction",
                message=(
                    f"Realization '{r.id}': source layer '{src.layer}' is above "
                    f"target layer '{tgt.layer}'. Realization goes from lower to higher layer."
                ),
                relationship_id=r.id,
                severity="warning",
            ))
        if r.type == "Serving" and src_order > tgt_order:
            out.append(ValidationViolation(
                rule="serving_direction",
                message=(
                    f"Serving '{r.id}': source layer '{src.layer}' is above "
                    f"target layer '{tgt.layer}'. Serving typically goes from lower to higher layer."
                ),
                relationship_id=r.id,
                severity="warning",
            ))
    return out


def _check_viewpoint_constraints(model: ArchiMateModel, viewpoint: str) -> list[ValidationViolation]:
    vp = VIEWPOINTS.get(viewpoint)
    if not vp:
        return [ValidationViolation(
            rule="viewpoint_unknown",
            message=f"Unknown viewpoint '{viewpoint}'",
            severity="warning",
        )]
    out = []
    allowed_elements: list[str] = vp.get("element_types", [])
    allowed_relationships: list[str] = vp.get("relationship_types", [])
    if allowed_elements:
        for e in model.elements:
            if e.type not in allowed_elements:
                out.append(ValidationViolation(
                    rule="viewpoint_element",
                    message=(
                        f"Element type '{e.type}' ('{e.name}') not permitted "
                        f"in viewpoint '{viewpoint}'"
                    ),
                    element_id=e.id,
                    severity="warning",
                ))
    if allowed_relationships:
        for r in model.relationships:
            if r.type not in allowed_relationships:
                out.append(ValidationViolation(
                    rule="viewpoint_relationship",
                    message=(
                        f"Relationship type '{r.type}' ({r.id}) not permitted "
                        f"in viewpoint '{viewpoint}'"
                    ),
                    relationship_id=r.id,
                    severity="warning",
                ))
    return out
