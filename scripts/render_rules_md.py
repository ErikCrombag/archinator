#!/usr/bin/env python3
"""
Render validation/rules.py into a clean Markdown reference for LLM system prompts.

Output: data/semantic_core.md  (or DATA_DIR env var / --output flag)

Run:
    python scripts/render_rules_md.py
    python scripts/render_rules_md.py --output /some/path/semantic_core.md
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Allow running from repo root or scripts/ dir without install
_repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(_repo_root / "backend" / "src"))

from archinator.validation.rules import (  # noqa: E402
    ANY,
    ELEMENT_TYPES,
    LAYER_ORDER,
    RELATIONSHIP_RULES,
    VIEWPOINTS,
)


def _element_table() -> list[str]:
    lines: list[str] = [
        "## Element Types",
        "",
        f"63 element types across 8 layers.",
        "",
    ]

    # Group by layer in stack order
    by_layer: dict[str, list[tuple[str, str]]] = {}
    for name, meta in ELEMENT_TYPES.items():
        by_layer.setdefault(meta["layer"], []).append((name, meta["aspect"]))

    for layer in sorted(by_layer, key=lambda l: LAYER_ORDER.get(l, 99)):
        lines.append(f"### {layer} Layer")
        lines.append("")
        lines.append("| Element | Aspect |")
        lines.append("|---|---|")
        for name, aspect in sorted(by_layer[layer]):
            lines.append(f"| {name} | {aspect} |")
        lines.append("")

    return lines


def _relationship_table() -> list[str]:
    lines: list[str] = [
        "## Relationship Rules",
        "",
        "Source/target aspects that are **directly** allowed per ArchiMate 3.2 §B.5.",
        "`ANY` = no aspect restriction.",
        "",
        "| Relationship | Source Aspect | Target Aspect | Cross-layer |",
        "|---|---|---|---|",
    ]

    for rel_type, rule in RELATIONSHIP_RULES.items():
        cross = "yes" if rule["cross_layer"] else "no"
        for src, tgt in rule["allowed_pairs"]:
            s = "ANY" if src == ANY else src
            t = "ANY" if tgt == ANY else tgt
            lines.append(f"| {rel_type} | {s} | {t} | {cross} |")

    lines.append("")
    lines.append(
        "> Association is always valid between any two elements (ANY→ANY)."
    )
    lines.append(
        "> Composition, Aggregation, Specialization always valid between same element type."
    )
    lines.append("")

    return lines


def _notes_section() -> list[str]:
    return [
        "## Key Rules",
        "",
        "- **Assignment** direction: ActiveStructure → Behavior, ActiveStructure → ActiveStructure,"
        " ActiveStructure → PassiveStructure (deployment). Never Behavior → PassiveStructure.",
        "- **Access** source: Behavior or ActiveStructure. Target: always PassiveStructure.",
        "- **Influence** target: always a Motivation element."
        " Core/Strategy elements *influence* Motivation; Motivation does NOT influence Core.",
        "- **Realization** direction: lower/more-concrete element → higher/more-abstract."
        " Includes Artifact → ApplicationComponent.",
        "- **Serving** direction: Behavior or ActiveStructure → Behavior or ActiveStructure.",
        "- **Triggering / Flow**: Behavior elements (and Junctions). Flow also allows PassiveStructure endpoints.",
        "- **Cross-layer**: Assignment and Specialization are same-layer only.",
        "- Layer stack (low→high): Physical → Technology → Application → Business → Strategy."
        " Motivation and Implementation are orthogonal.",
        "",
    ]


def _viewpoints_section() -> list[str]:
    lines: list[str] = [
        "## Standard Viewpoints",
        "",
        "Empty element/relationship list means *all allowed*.",
        "",
    ]

    for vp_name, vp in VIEWPOINTS.items():
        el = ", ".join(vp["element_types"]) if vp["element_types"] else "all"
        rel = ", ".join(vp["relationship_types"]) if vp["relationship_types"] else "all"
        lines.append(f"**{vp_name}** — {vp['description']}")
        lines.append(f"- Elements: {el}")
        lines.append(f"- Relationships: {rel}")
        lines.append("")

    return lines


def render() -> str:
    sections: list[str] = [
        "# ArchiMate 3.2 Semantic Core Reference",
        "",
        "> Auto-generated from `validation/rules.py` — do not edit manually.",
        "> Reflects the ArchiMate 3.2 specification (The Open Group).",
        "",
    ]
    sections += _notes_section()
    sections += _element_table()
    sections += _relationship_table()
    sections += _viewpoints_section()
    return "\n".join(sections)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render rules.py → semantic_core.md")
    default_out = Path(
        os.environ.get("DATA_DIR", str(_repo_root / "data"))
    ) / "rules_core.md"
    parser.add_argument("--output", type=Path, default=default_out)
    args = parser.parse_args()

    content = render()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content, encoding="utf-8")
    print(f"[render_rules_md] wrote {len(content):,} chars to {args.output}")


if __name__ == "__main__":
    main()
