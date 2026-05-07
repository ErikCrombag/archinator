from __future__ import annotations
import json
import uuid
import logging
from typing import Any

import httpx

from ..models import (
    ArchiMateModel, Element, Relationship, View,
    CompactionMode, OutputFormat, GenerationResult, ValidationResult,
)
from ..knowledge import rag
from ..validation import validator
from ..formatting import exchange_xml, json_fmt, mermaid as mermaid_fmt, plantuml as plantuml_fmt
from ..compaction.compact import compact_model
from .prompts import build_system_prompt, build_generation_prompt

log = logging.getLogger(__name__)

_FORMATTERS = {
    OutputFormat.EXCHANGE_XML: exchange_xml.render,
    OutputFormat.JSON: json_fmt.render,
    OutputFormat.MERMAID: mermaid_fmt.render,
    OutputFormat.PLANTUML: plantuml_fmt.render,
}

MAX_RETRIES = 3


async def generate(
    query: str,
    formats: list[OutputFormat],
    compaction: CompactionMode,
    viewpoint: str | None,
    existing_diagram: str | None,
    refinement_query: str | None,
    ollama_base_url: str,
    ollama_model: str,
) -> GenerationResult:
    rag_chunks = rag.query(query, n_results=5)

    system_prompt = build_system_prompt()
    user_prompt = build_generation_prompt(
        query=query,
        rag_chunks=rag_chunks,
        viewpoint=viewpoint,
        existing_diagram=existing_diagram,
        refinement_query=refinement_query,
    )

    model = await _generate_with_retries(
        system_prompt, user_prompt, ollama_base_url, ollama_model, viewpoint
    )

    full_validation = validator.validate(model, viewpoint=viewpoint)

    if compaction != CompactionMode.FULL:
        compact = compact_model(model, compaction, viewpoint)
        compact_val = validator.validate(compact, viewpoint=viewpoint)
        output_model = compact
        compact_validation = compact_val
    else:
        output_model = model
        compact_validation = None

    outputs: dict[str, str] = {}
    for fmt in formats:
        renderer = _FORMATTERS.get(fmt)
        if renderer:
            try:
                outputs[fmt.value] = renderer(output_model)
            except Exception as exc:
                log.error("Formatter %s failed: %s", fmt, exc)
                outputs[fmt.value] = f"# Render error: {exc}"

    return GenerationResult(
        model=model,
        validation=full_validation,
        outputs=outputs,
        compaction_mode=compaction,
        compact_validation=compact_validation,
        rag_chunks_used=rag_chunks,
    )


async def _generate_with_retries(
    system_prompt: str,
    user_prompt: str,
    base_url: str,
    model_name: str,
    viewpoint: str | None,
) -> ArchiMateModel:
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            raw = await _call_ollama(system_prompt, user_prompt, base_url, model_name)
            model = _parse_model_json(raw)
            result = validator.validate(model, viewpoint=viewpoint)
            if result.valid:
                return model
            # Feed violations back for self-correction
            violation_text = "\n".join(
                f"- [{v.rule}] {v.message}" for v in result.errors()
            )
            log.warning("Attempt %d: %d violations, retrying with feedback", attempt + 1, len(result.errors()))
            user_prompt = (
                f"{user_prompt}\n\n"
                f"## Previous attempt had validation errors — fix ALL of them:\n{violation_text}"
            )
        except Exception as exc:
            last_error = exc
            log.warning("Attempt %d failed: %s", attempt + 1, exc)

    # Return the last model even if invalid (caller inspects validation result)
    if last_error:
        raise last_error
    raw = await _call_ollama(system_prompt, user_prompt, base_url, model_name)
    return _parse_model_json(raw)


async def _call_ollama(
    system_prompt: str,
    user_prompt: str,
    base_url: str,
    model_name: str,
) -> str:
    payload: dict[str, Any] = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.2,
            "num_predict": 8192,
        },
    }
    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(f"{base_url}/api/chat", json=payload)
        r.raise_for_status()
        return r.json()["message"]["content"]


def _parse_model_json(raw: str) -> ArchiMateModel:
    # Strip any accidental markdown fences
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0]

    data: dict[str, Any] = json.loads(raw)

    elements = [
        Element(
            id=e["id"],
            type=e["type"],
            name=e["name"],
            layer=e["layer"],
            aspect=e["aspect"],
            description=e.get("description"),
            properties=e.get("properties", {}),
        )
        for e in data.get("elements", [])
    ]

    relationships = [
        Relationship(
            id=r["id"],
            type=r["type"],
            source_id=r["source_id"],
            target_id=r["target_id"],
            name=r.get("name"),
            access_type=r.get("access_type"),
            influence_modifier=r.get("influence_modifier"),
            properties=r.get("properties", {}),
        )
        for r in data.get("relationships", [])
    ]

    views = [
        View(
            id=v["id"],
            name=v["name"],
            viewpoint=v.get("viewpoint"),
            element_ids=v.get("element_ids", []),
            relationship_ids=v.get("relationship_ids", []),
        )
        for v in data.get("views", [])
    ]

    return ArchiMateModel(
        id=data.get("id", str(uuid.uuid4())),
        name=data.get("name", "Untitled Model"),
        elements=elements,
        relationships=relationships,
        views=views,
        metadata=data.get("metadata", {}),
    )
