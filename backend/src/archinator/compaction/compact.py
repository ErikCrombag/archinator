from __future__ import annotations
import copy
from ..models import ArchiMateModel, Element, Relationship, View, CompactionMode
from ..validation.rules import VIEWPOINTS, ABSTRACTION_PRIORITY


def compact_model(
    model: ArchiMateModel,
    mode: CompactionMode,
    viewpoint: str | None = None,
) -> ArchiMateModel:
    """
    Return a new compacted ArchiMateModel.
    Original model is not mutated.
    """
    compacted = copy.deepcopy(model)
    if mode == CompactionMode.VIEWPOINT:
        compacted = _compact_viewpoint(compacted, viewpoint)
    elif mode == CompactionMode.ABSTRACTION:
        compacted = _compact_abstraction(compacted)
    return compacted


# ── Viewpoint compaction ──────────────────────────────────────────────────────

def _compact_viewpoint(model: ArchiMateModel, viewpoint: str | None) -> ArchiMateModel:
    """Remove elements and relationships not permitted in the viewpoint."""
    if not viewpoint:
        return model
    vp = VIEWPOINTS.get(viewpoint)
    if not vp:
        return model

    allowed_elements: list[str] = vp.get("element_types", [])
    allowed_relationships: list[str] = vp.get("relationship_types", [])

    if allowed_elements:
        kept_ids = {e.id for e in model.elements if e.type in allowed_elements}
        model.elements = [e for e in model.elements if e.id in kept_ids]
    else:
        kept_ids = {e.id for e in model.elements}

    if allowed_relationships:
        model.relationships = [
            r for r in model.relationships
            if r.type in allowed_relationships
            and r.source_id in kept_ids
            and r.target_id in kept_ids
        ]
    else:
        model.relationships = [
            r for r in model.relationships
            if r.source_id in kept_ids and r.target_id in kept_ids
        ]

    model.views = _trim_views(model.views, kept_ids, {r.id for r in model.relationships})
    return model


# ── Abstraction compaction ────────────────────────────────────────────────────

def _compact_abstraction(model: ArchiMateModel) -> ArchiMateModel:
    """
    Remove low-priority elements and redirect their relationships to the nearest
    higher-priority element, per ArchiMate abstraction rules.

    Strategy:
    1. Rank elements by ABSTRACTION_PRIORITY (lower = collapse first).
    2. Elements with priority < threshold are candidates for removal.
    3. For each removed element, redirect its relationships to:
       - the element it served/realized/assigned-to (its "parent" in the diagram)
       - or drop the relationship if no valid redirect exists.
    4. Remove self-loops introduced by redirects.
    """
    THRESHOLD = 4  # priority < threshold → candidate for removal

    candidates = {
        e.id for e in model.elements
        if ABSTRACTION_PRIORITY.get(e.type, 10) < THRESHOLD
    }

    if not candidates:
        return model

    # Build redirect map: candidate_id → best surviving neighbor id
    redirect: dict[str, str | None] = {}
    for cid in candidates:
        redirect[cid] = _find_redirect_target(cid, candidates, model)

    # Remove candidates
    kept_ids = {e.id for e in model.elements if e.id not in candidates}
    model.elements = [e for e in model.elements if e.id in kept_ids]

    # Redirect or drop relationships
    new_rels: list[Relationship] = []
    for r in model.relationships:
        src = redirect.get(r.source_id, r.source_id) if r.source_id in candidates else r.source_id
        tgt = redirect.get(r.target_id, r.target_id) if r.target_id in candidates else r.target_id
        if src is None or tgt is None:
            continue
        if src not in kept_ids or tgt not in kept_ids:
            continue
        if src == tgt:
            continue  # drop self-loops
        new_rels.append(Relationship(
            id=r.id, type=r.type, source_id=src, target_id=tgt,
            name=r.name, properties=r.properties,
        ))

    # Deduplicate relationships by (type, source, target)
    seen: set[tuple] = set()
    deduped: list[Relationship] = []
    for r in new_rels:
        key = (r.type, r.source_id, r.target_id)
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    model.relationships = deduped
    model.views = _trim_views(model.views, kept_ids, {r.id for r in deduped})
    return model


def _find_redirect_target(
    eid: str,
    candidates: set[str],
    model: ArchiMateModel,
) -> str | None:
    """Find the nearest non-candidate element connected to eid."""
    for r in model.relationships:
        if r.source_id == eid and r.target_id not in candidates:
            return r.target_id
        if r.target_id == eid and r.source_id not in candidates:
            return r.source_id
    return None


def _trim_views(
    views: list[View],
    kept_element_ids: set[str],
    kept_rel_ids: set[str],
) -> list[View]:
    for v in views:
        v.element_ids = [eid for eid in v.element_ids if eid in kept_element_ids]
        v.relationship_ids = [rid for rid in v.relationship_ids if rid in kept_rel_ids]
    return views
