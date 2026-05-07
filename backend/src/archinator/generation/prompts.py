from __future__ import annotations
from ..knowledge.core import load_semantic_core
from ..validation.rules import ELEMENT_TYPES, RELATIONSHIP_TYPES, VIEWPOINTS

_ELEMENT_LIST = ", ".join(sorted(ELEMENT_TYPES.keys()))
_RELATIONSHIP_LIST = ", ".join(sorted(RELATIONSHIP_TYPES))
_VIEWPOINT_LIST = ", ".join(sorted(VIEWPOINTS.keys()))

SYSTEM_PROMPT = """\
You are an ArchiMate 3.2 expert that generates valid architectural diagrams.

## Your task
Given a user query, produce a complete ArchiMate 3.2 model as a single JSON object.
The model MUST be valid according to ArchiMate 3.2 rules.

## Output format
Return ONLY a JSON object — no prose, no markdown fences, no explanation.
Schema:
{{
  "id": "<uuid>",
  "name": "<model name>",
  "elements": [
    {{
      "id": "<unique_id>",
      "type": "<ArchiMate element type>",
      "name": "<element name>",
      "layer": "<layer>",
      "aspect": "<aspect>",
      "description": "<optional description or null>"
    }}
  ],
  "relationships": [
    {{
      "id": "<unique_id>",
      "type": "<ArchiMate relationship type>",
      "source_id": "<element id>",
      "target_id": "<element id>",
      "name": "<optional name or null>"
    }}
  ],
  "views": [
    {{
      "id": "<unique_id>",
      "name": "<view name>",
      "viewpoint": "<viewpoint name or null>",
      "element_ids": ["<id>", ...],
      "relationship_ids": ["<id>", ...]
    }}
  ]
}}

## Valid element types
{element_list}

## Valid relationship types
{relationship_list}

## Valid viewpoints
{viewpoint_list}

## Strict rules
- Use ONLY element types from the list above. Never invent new types.
- Use ONLY relationship types from the list above.
- Assign correct layer and aspect to every element.
- Relationship source_id and target_id MUST reference existing element ids.
- Apply correct layer directionality: Realization goes from lower to higher layer.
  Serving goes from provider layer to consumer layer (typically lower to higher).
- Composition/Aggregation must respect containment semantics.
- Every element id and relationship id must be unique within the model.
- If a viewpoint is requested, include only elements and relationships valid for that viewpoint.

## ArchiMate 3.2 Semantic Core Reference
{semantic_core}
"""


def build_system_prompt() -> str:
    return SYSTEM_PROMPT.format(
        element_list=_ELEMENT_LIST,
        relationship_list=_RELATIONSHIP_LIST,
        viewpoint_list=_VIEWPOINT_LIST,
        semantic_core=load_semantic_core(),
    )


def build_generation_prompt(
    query: str,
    rag_chunks: list[str],
    viewpoint: str | None,
    existing_diagram: str | None,
    refinement_query: str | None,
) -> str:
    parts: list[str] = []

    if rag_chunks:
        parts.append("## Relevant spec excerpts\n" + "\n\n---\n\n".join(rag_chunks))

    if existing_diagram and refinement_query:
        parts.append(
            f"## Existing diagram to refine\n```\n{existing_diagram}\n```\n\n"
            f"## Refinement instruction\n{refinement_query}"
        )
    else:
        parts.append(f"## User query\n{query}")

    if viewpoint:
        parts.append(f"## Required viewpoint\n{viewpoint}")
        parts.append(
            f"Only include element types and relationship types valid for the '{viewpoint}' viewpoint."
        )

    parts.append(
        "Generate a complete, valid ArchiMate 3.2 model as JSON. "
        "Be thorough — include all relevant elements and relationships needed to meaningfully "
        "answer the query. Do not omit elements just to keep it short."
    )

    return "\n\n".join(parts)
