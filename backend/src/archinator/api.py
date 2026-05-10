"""FastAPI HTTP layer — wraps MCP tools for browser + programmatic access."""
from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Security, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import settings
from .models import CompactionMode, OutputFormat
from .generation import pipeline
from .generation.pipeline import OllamaTimeoutError
from .validation import validator as val_module
from .validation.rules import VIEWPOINTS
from .knowledge import rag as rag_module
from .auth import api_keys
from . import _parse_diagram_input

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await api_keys.init_db()
    yield


app = FastAPI(
    title="Archinator",
    description="ArchiMate 3.2 diagram generation API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Caddy handles origin restriction externally
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Auth dependency ───────────────────────────────────────────────────────────

async def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> Any:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")
    record = await api_keys.validate_key(x_api_key)
    if not record:
        raise HTTPException(status_code=403, detail="Invalid or revoked API key")
    return record


# ── Request/Response models ───────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    query: str
    formats: list[str] = Field(default=["exchange_xml"])
    compaction: str = Field(default="full")
    viewpoint: str | None = None
    existing_diagram: str | None = None
    refinement_query: str | None = None


class ValidateRequest(BaseModel):
    diagram: str
    format: str
    viewpoint: str | None = None


class QuerySpecRequest(BaseModel):
    question: str
    n_results: int = 5


class CreateKeyRequest(BaseModel):
    name: str


# ── Diagram endpoints ─────────────────────────────────────────────────────────

@app.post("/generate")
async def generate_diagram(
    req: GenerateRequest,
    _auth=Depends(require_api_key),
):
    try:
        formats = [OutputFormat(f) for f in req.formats]
        compaction = CompactionMode(req.compaction)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    try:
        result = await pipeline.generate(
            query=req.query,
            formats=formats,
            compaction=compaction,
            viewpoint=req.viewpoint,
            existing_diagram=req.existing_diagram,
            refinement_query=req.refinement_query,
            ollama_base_url=settings.ollama_base_url,
            ollama_model=settings.ollama_model,
            ollama_num_ctx=settings.ollama_num_ctx,
        )
    except OllamaTimeoutError as exc:
        log.error("Ollama generation timed out: %s", exc)
        raise HTTPException(status_code=504, detail=str(exc))

    response: dict = {
        "model_name": result.model.name,
        "valid": result.validation.valid,
        "best_effort": result.best_effort,
        "attempts": result.attempts,
        "violations": [
            {"rule": v.rule, "message": v.message, "severity": v.severity}
            for v in result.validation.violations
        ],
        "compaction": result.compaction_mode.value,
        "outputs": result.outputs,
    }
    if result.best_effort:
        error_count = len(result.validation.errors())
        response["warning"] = (
            f"All {result.attempts} generation attempt(s) exhausted without producing valid "
            f"ArchiMate 3.2. This output is BEST-EFFORT ONLY and contains {error_count} "
            f"validation error(s). Do not use in production diagrams without manual review."
        )
    if result.compact_validation:
        response["compact_valid"] = result.compact_validation.valid
        response["compact_violations"] = [
            {"rule": v.rule, "message": v.message, "severity": v.severity}
            for v in result.compact_validation.violations
        ]
    return response


@app.post("/validate")
async def validate_diagram(
    req: ValidateRequest,
    _auth=Depends(require_api_key),
):
    try:
        model = _parse_diagram_input(req.diagram, req.format)
        result = val_module.validate(model, viewpoint=req.viewpoint)
        return {
            "valid": result.valid,
            "violations": [
                {"rule": v.rule, "message": v.message, "severity": v.severity,
                 "element_id": v.element_id, "relationship_id": v.relationship_id}
                for v in result.violations
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/query-spec")
async def query_spec(
    req: QuerySpecRequest,
    _auth=Depends(require_api_key),
):
    chunks = rag_module.query(req.question, n_results=req.n_results)
    return {"chunks": chunks, "index_available": rag_module.index_available()}


@app.get("/formats")
async def list_formats(_auth=Depends(require_api_key)):
    return {
        "formats": {
            "exchange_xml": "Open Group ArchiMate 3 Exchange Format XML",
            "json": "Archinator internal JSON schema",
            "mermaid": "Mermaid graph diagram",
            "plantuml": "PlantUML ArchiMate diagram",
        }
    }


@app.get("/viewpoints")
async def list_viewpoints(_auth=Depends(require_api_key)):
    return {
        "viewpoints": {
            name: vp.get("description", "")
            for name, vp in VIEWPOINTS.items()
        }
    }


# ── Admin endpoints (Authentik role check happens at Caddy / middleware layer) ──

@app.post("/admin/keys")
async def create_api_key(req: CreateKeyRequest, _auth=Depends(require_api_key)):
    raw, record = await api_keys.create_key(name=req.name)
    return {
        "id": record.id,
        "name": record.name,
        "key": raw,  # shown once
        "prefix": record.key_prefix,
        "created_at": record.created_at.isoformat(),
    }


@app.get("/admin/keys")
async def list_api_keys(_auth=Depends(require_api_key)):
    keys = await api_keys.list_keys()
    return {
        "keys": [
            {
                "id": k.id,
                "name": k.name,
                "prefix": k.key_prefix,
                "active": k.active,
                "created_at": k.created_at.isoformat(),
                "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
                "use_count": k.use_count,
            }
            for k in keys
        ]
    }


@app.delete("/admin/keys/{key_id}")
async def revoke_api_key(key_id: int, _auth=Depends(require_api_key)):
    ok = await api_keys.revoke_key(key_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Key not found")
    return {"revoked": True}


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "rag_index": rag_module.index_available()}


def main() -> None:
    import uvicorn
    logging.basicConfig(level=settings.log_level)
    uvicorn.run("archinator.api:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
