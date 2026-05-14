from __future__ import annotations
import json
import os
import uuid
import logging
from pathlib import Path
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
from .schema import build_ollama_schema

log = logging.getLogger(__name__)


class OllamaTimeoutError(Exception):
    """Raised when the Ollama /api/chat endpoint does not respond in time."""

class OllamaConnectionError(Exception):
    """Raised when the Ollama /api/chat endpoint cannot be reached or returns an unexpected error."""


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
    ollama_num_ctx: int = 65536,
    ollama_api_key: str = "",
) -> GenerationResult:
    rag_chunks = rag.query(query, n_results=5)

    log.info(
        "Starting pipeline: url=%s model=%s num_ctx=%d api_key=%s",
        ollama_base_url, ollama_model, ollama_num_ctx,
        "set" if ollama_api_key else "not set",
    )

    log.debug("RAG query result:\n%s", '\n\t'.join(rag_chunks))

    system_prompt = build_system_prompt()
    user_prompt = build_generation_prompt(
        query=query,
        rag_chunks=rag_chunks,
        viewpoint=viewpoint,
        existing_diagram=existing_diagram,
        refinement_query=refinement_query,
    )

    log.debug("Prompts built (system=%d chars, user=%d chars)", len(system_prompt), len(user_prompt))

    model, attempts = await _generate_with_retries(
        system_prompt, user_prompt, ollama_base_url, ollama_model, viewpoint, ollama_num_ctx, ollama_api_key
    )

    log.debug('Generated model')

    full_validation = validator.validate(model, viewpoint=viewpoint)
    best_effort = not full_validation.valid
    if best_effort:
        log.error(
            "All %d attempt(s) exhausted — returning best-effort INVALID model (%d errors).",
            attempts, len(full_validation.errors()),
        )
    else:
        log.info("Valid model generated in %d attempt(s).", attempts)

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
        best_effort=best_effort,
        attempts=attempts,
    )


async def _generate_with_retries(
    system_prompt: str,
    user_prompt: str,
    base_url: str,
    model_name: str,
    viewpoint: str | None,
    num_ctx: int = 65536,
    api_key: str = "",
) -> tuple[ArchiMateModel, int]:
    """
    Self-correcting generation loop using multi-turn conversation.

    On each failure the LLM's previous response is added as an 'assistant'
    message and the validation errors are added as a 'user' message, giving
    the model full context to fix exactly what it produced.

    Returns (best_model, attempts_used).  If all retries fail the last
    successfully-parsed model (even if invalid) is returned; if parsing
    never succeeded a final unconstrained call is made.
    """
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_prompt},
    ]

    best_model: ArchiMateModel | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        log.debug("Generation attempt %d/%d", attempt, MAX_RETRIES)
        raw = await _call_ollama(messages, base_url, model_name, num_ctx, api_key)

        # ── Parse ─────────────────────────────────────────────────────────────
        try:
            model = _parse_model_json(raw)
        except Exception as exc:
            log.warning("Attempt %d/%d: JSON parse error: %s", attempt, MAX_RETRIES, exc)
            if attempt < MAX_RETRIES:
                messages.append({"role": "assistant", "content": raw})
                messages.append({
                    "role": "user",
                    "content": (
                        "Your response was not valid JSON.\n"
                        f"Parse error: {exc}\n\n"
                        "Return ONLY a valid JSON object matching the schema. "
                        "No markdown fences, no prose."
                    ),
                })
            continue

        best_model = model

        # ── Validate ──────────────────────────────────────────────────────────
        result = validator.validate(model, viewpoint=viewpoint)
        if result.valid:
            log.info("Attempt %d/%d: valid model generated.", attempt, MAX_RETRIES)
            return model, attempt

        errors = result.errors()
        log.warning(
            "Attempt %d/%d: %d validation error(s) — feeding back to LLM",
            attempt, MAX_RETRIES, len(errors),
        )

        if attempt < MAX_RETRIES:
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": _correction_prompt(errors),
            })

    # ── All retries exhausted ─────────────────────────────────────────────────
    if best_model is not None:
        log.warning("All %d retries exhausted; returning best (invalid) model.", MAX_RETRIES)
        return best_model, MAX_RETRIES

    # Parsing never succeeded — one final attempt with the accumulated context
    log.warning("Parsing never succeeded; making final unconstrained attempt.")
    raw = await _call_ollama(messages, base_url, model_name, num_ctx, api_key)
    return _parse_model_json(raw), MAX_RETRIES + 1


def _correction_prompt(errors: list) -> str:
    """
    Format validation errors into a clear, actionable correction request.
    Groups by rule type so the LLM sees a structured fix list.
    """
    by_rule: dict[str, list[str]] = {}
    for v in errors:
        by_rule.setdefault(v.rule, []).append(v.message)

    lines = [
        "Your previous model has validation errors. Fix ALL of them and return "
        "the complete corrected JSON (not just the changed parts).\n",
        "## Validation errors",
    ]
    for rule, messages in by_rule.items():
        lines.append(f"\n### {rule}")
        for msg in messages:
            lines.append(f"- {msg}")

    lines.append(
        "\n## Instructions\n"
        "- Return ONLY the corrected JSON object.\n"
        "- Keep all elements and relationships that are already valid.\n"
        "- Fix only the elements/relationships listed above.\n"
        "- Do not add or remove elements unless required to fix an error."
    )
    return "\n".join(lines)


async def _call_ollama(
    messages: list[dict[str, str]],
    base_url: str,
    model_name: str,
    num_ctx: int = 65536,
    api_key: str = "",
) -> str:
    """Call Ollama /api/chat with a full message history."""
    import time

    url = f"{base_url.rstrip('/')}/api/chat"
    payload: dict[str, Any] = {
        "model": model_name,
        "messages": messages,
        "stream": False,
        "format": build_ollama_schema(),
        "options": {
            "temperature": 0.2,
            "num_predict": 8192,
            "num_ctx": num_ctx,
        },
    }
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    log.debug(
        "POST %s  model=%s  messages=%d  auth=%s",
        url, model_name, len(messages),
        "Bearer ***" if api_key else "none",
    )

    _timeout = httpx.Timeout(connect=10.0, read=600.0, write=30.0, pool=10.0)
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=_timeout) as client:
            r = await client.post(url, json=payload, headers=headers)
            elapsed = time.monotonic() - t0
            log.debug("Response: status=%d  elapsed=%.1fs", r.status_code, elapsed)
            if r.status_code >= 400:
                log.error(
                    "Ollama error %d from %s — body: %s",
                    r.status_code, url, r.text[:500],
                )
            r.raise_for_status()
            data = r.json()
            response_text = data["message"]["content"]
            if not response_text or not response_text.strip():
                log.error("Ollama returned empty content. Full response: %s", data)
                raise ValueError("Ollama returned empty content")
            log.debug("Response content length: %d chars", len(response_text))
            if os.environ.get("PROMPT_LOG"):
                _write_prompt_log(messages, response_text)
            return response_text
    except httpx.ConnectError as exc:
        log.error("Connection failed to %s: %s", url, exc)
        raise OllamaConnectionError(f"Cannot connect to Ollama at {url}: {exc}") from exc
    except httpx.ReadTimeout as exc:
        log.error("Read timeout after %.1fs from %s", time.monotonic() - t0, url)
        raise OllamaTimeoutError(
            "Ollama did not return a response within 600 s. "
            "The model may be too slow for the requested token budget on this hardware."
        ) from exc
    except httpx.HTTPStatusError as exc:
        log.error("HTTP error from %s: %s", url, exc)
        raise OllamaConnectionError(
            f"Ollama returned HTTP {exc.response.status_code}: {exc.response.text[:300]}"
        ) from exc
    except (KeyError, ValueError) as exc:
        log.error("Unexpected Ollama response shape from %s: %s", url, exc)
        raise OllamaConnectionError(f"Unexpected Ollama response: {exc}") from exc


_LOG_PATH = Path(os.environ.get("PROMPT_LOG", "prompt.log"))
_prompt_call_count = 0


def _write_prompt_log(messages: list[dict[str, str]], response: str) -> None:
    global _prompt_call_count
    _prompt_call_count += 1
    sep = "=" * 80
    with _LOG_PATH.open("w", encoding="utf-8") as f:
        f.write(f"# Ollama prompt log — call {_prompt_call_count}\n\n")
        for msg in messages:
            f.write(f"{sep}\n## [{msg['role'].upper()}]\n{sep}\n{msg['content']}\n\n")
        f.write(f"{sep}\n## [RESPONSE]\n{sep}\n{response}\n")


def _parse_model_json(raw: str) -> ArchiMateModel:
    # Strip any accidental markdown fences
    raw = raw.strip()
    if not raw:
        raise ValueError("Model returned empty response — cannot parse JSON")

    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0]

    raw = raw.strip()
    if not raw:
        raise ValueError("Response contained only a markdown fence with no JSON body")

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
