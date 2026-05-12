from __future__ import annotations
from ..models import ArchiMateModel

# ArchiMate layer → Mermaid subgraph label
_LAYER_LABELS = {
    "Strategy": "Strategy",
    "Business": "Business",
    "Application": "Application",
    "Technology": "Technology",
    "Physical": "Physical",
    "Motivation": "Motivation",
    "Implementation": "Implementation & Migration",
    "Composite": "Composite",
}

# Relationship type → Mermaid arrow style
# Mermaid flowchart arrows mapped to ArchiMate 3.2 visual notation:
#   Structural:  solid lines  (--o diamond-ish, --> arrow)
#   Dependency:  dashed lines (-.->)
#   Dynamic:     thick (==>) for Triggering, dashed for Flow
#   Other:       solid for Specialization
_ARROW = {
    "Composition":   "--o",   # hollow circle ≈ diamond (Mermaid has no diamond)
    "Aggregation":   "--o",   # same — Mermaid doesn't distinguish filled/hollow diamond
    "Assignment":    "o-->",  # circle at source, arrow at target
    "Realization":   "-.->",  # dashed, open arrowhead
    "Serving":       "-.->",  # dashed, open arrowhead (dependency)
    "Access":        "-.->",  # dashed, open arrowhead
    "Influence":     "-.->",  # dashed, open arrowhead
    "Association":   "-->",   # solid, open arrowhead
    "Triggering":    "==>",   # thick solid (dynamic)
    "Flow":          "-.->",  # dashed (dynamic dependency)
    "Specialization":"-->",   # solid, open arrowhead (closest to hollow triangle)
}


def render(model: ArchiMateModel) -> str:
    lines = ["graph LR"]

    # Group elements by layer
    layers: dict[str, list] = {}
    for e in model.elements:
        layers.setdefault(e.layer, []).append(e)

    for layer, elems in layers.items():
        label = _LAYER_LABELS.get(layer, layer)
        lines.append(f'  subgraph {label}')
        for e in elems:
            safe_id = _safe_id(e.id)
            label_text = f"{e.name}\\n[{e.type}]"
            lines.append(f'    {safe_id}["{label_text}"]')
        lines.append("  end")

    lines.append("")

    for r in model.relationships:
        src = _safe_id(r.source_id)
        tgt = _safe_id(r.target_id)
        arrow = _ARROW.get(r.type, "-->")
        label = f'|{r.type}|' if r.name is None else f'|{r.type}: {r.name}|'
        lines.append(f"  {src} {arrow}{label} {tgt}")

    return "\n".join(lines)


def _safe_id(eid: str) -> str:
    return eid.replace("-", "_").replace(".", "_")
