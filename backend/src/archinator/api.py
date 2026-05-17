"""FastAPI HTTP layer — wraps MCP tools for browser + programmatic access."""
from __future__ import annotations
import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Annotated, Any

import httpx
from fastapi import FastAPI, HTTPException, Security, Header, Depends, Request
from fastapi.responses import Response
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
from mcp.server.sse import SseServerTransport
from sse_starlette.sse import EventSourceResponse as _EventSourceResponse
from .server import app as mcp_server, list_tools as _mcp_list_tools

# Default is 15 s — matches the MCP client's read timeout exactly, causing a
# race where the client gives up and reconnects before the ping arrives.
# 3 s keeps the SSE alive comfortably through long LLM generation runs.
_EventSourceResponse.DEFAULT_PING_INTERVAL = 3

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


_sse = SseServerTransport("/mcp/messages/")


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
    log.debug(f"Starting generation of diagram via /generate API call.\nFormats: {'.'.join(req.formats)}\nCompaction: {req.compaction}\nViewpoint: {req.viewpoint}")

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
            ollama_api_key=settings.ollama_api_key,
        )
    except OllamaTimeoutError as exc:
        log.error("Ollama timeout: %s", exc)
        raise HTTPException(status_code=504, detail=str(exc))
    except pipeline.OllamaConnectionError as exc:
        log.error("Ollama connection error: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        log.exception("Generation failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Generation failed: {type(exc).__name__}: {exc}",
        )

    log.debug("Ollama generation completed")

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


# ── PlantUML render — local JAR preferred, kroki.io fallback ─────────────────

async def _render_plantuml_jar(source: str, jar_path: str) -> bytes:
    """Render PlantUML source to SVG via local JAR (subprocess, async)."""
    proc = await asyncio.create_subprocess_exec(
        "java", "-jar", jar_path, "-tsvg", "-pipe", "-charset", "UTF-8",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(source.encode("utf-8")), timeout=60)
    if proc.returncode != 0:
        err = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"PlantUML JAR error (exit {proc.returncode}): {err[:300]}")
    return stdout


async def _render_plantuml_kroki(source: str) -> bytes:
    """Render PlantUML source to SVG via kroki.io (fallback)."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            "https://kroki.io/plantuml/svg",
            content=source.encode("utf-8"),
            headers={"Content-Type": "text/plain"},
        )
        r.raise_for_status()
        return r.content


@app.post("/preview/plantuml")
async def preview_plantuml(request: Request, _auth=Depends(require_api_key)):
    source = (await request.body()).decode("utf-8")
    if not source.strip():
        raise HTTPException(status_code=422, detail="Empty diagram source")

    jar_path = settings.plantuml_jar
    use_jar = os.path.isfile(jar_path)

    try:
        if use_jar:
            log.debug("Rendering PlantUML via local JAR: %s", jar_path)
            svg = await _render_plantuml_jar(source, jar_path)
        else:
            log.debug("PlantUML JAR not found at %s — falling back to kroki.io", jar_path)
            svg = await _render_plantuml_kroki(source)
        return Response(content=svg, media_type="image/svg+xml")
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="PlantUML render timed out")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="kroki.io timed out")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502,
                            detail=f"kroki.io {exc.response.status_code}: {exc.response.text[:300]}")
    except Exception as exc:
        log.error("PlantUML render error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── MCP tools schema ─────────────────────────────────────────────────────────

@app.get("/mcp/tools")
async def mcp_tools(_auth=Depends(require_api_key)):
    tools = await _mcp_list_tools()
    return {
        "tools": [
            {"name": t.name, "description": t.description, "inputSchema": t.inputSchema}
            for t in tools
        ]
    }


# ── MCP over SSE ─────────────────────────────────────────────────────────────

class _AsgiHandledResponse(Response):
    """connect_sse / handle_post_message already sent the ASGI response.
    Return this so FastAPI does not attempt a second http.response.start."""
    async def __call__(self, scope, receive, send) -> None:
        pass


@app.get("/mcp")
async def mcp_sse(request: Request, _auth=Depends(require_api_key)):
    client_ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )
    user_agent = request.headers.get("user-agent", "unknown")
    t0 = time.monotonic()
    log.info("[MCP] SSE OPEN client=%s ua=%s", client_ip, user_agent)
    try:
        async with _sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            log.debug("[MCP] SSE streams established, entering mcp_server.run() client=%s", client_ip)
            await mcp_server.run(
                streams[0], streams[1],
                mcp_server.create_initialization_options(),
            )
            log.debug("[MCP] SSE mcp_server.run() returned normally client=%s", client_ip)
    except BaseException as exc:
        log.error("[MCP] SSE mcp_server.run() raised %s: %s  client=%s  elapsed=%.2fs",
                  type(exc).__name__, exc, client_ip, time.monotonic() - t0)
        if not isinstance(exc, Exception):
            raise
    finally:
        log.info("[MCP] SSE CLOSE client=%s duration=%.2fs", client_ip, time.monotonic() - t0)
    return _AsgiHandledResponse()


@app.post("/mcp/messages/")
async def mcp_messages(request: Request, _auth=Depends(require_api_key)):
    await _sse.handle_post_message(request.scope, request.receive, request._send)
    return _AsgiHandledResponse()


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "rag_index": rag_module.index_available()}


def main() -> None:
    import uvicorn
    logging.basicConfig(level=settings.log_level)
    reload = os.getenv("DEV", "").lower() in ("1", "true", "yes")
    uvicorn.run("archinator.api:app", host="0.0.0.0", port=8000, reload=reload)


if __name__ == "__main__":
    main()
