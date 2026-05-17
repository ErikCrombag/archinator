"""MCP server — stdio transport."""
from __future__ import annotations
import asyncio
import base64
import contextlib
import json
import logging
import time

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.session import ServerSession
from mcp.types import Tool, TextContent, ImageContent

from .config import settings
from .models import CompactionMode, OutputFormat
from .generation import pipeline
from .validation import validator as val_module
from .validation.rules import VIEWPOINTS
from .knowledge import rag as rag_module
from .formatting.plantuml_render import render as _render_plantuml
from . import _parse_diagram_input

_IMAGE_FORMATS = {"image_svg", "image_png"}
_IMAGE_MIME = {"image_svg": "image/svg+xml", "image_png": "image/png"}
_IMAGE_FMT_ARG = {"image_svg": "svg", "image_png": "png"}

log = logging.getLogger(__name__)

app = Server("archinator")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="generate_diagram",
            description=(
                "Generate a valid ArchiMate 3.2 diagram from a natural language query. "
                "Returns the diagram in one or more output formats."
            ),
            inputSchema={
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string", "description": "Natural language description of the diagram to generate"},
                    "formats": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["exchange_xml", "json", "mermaid", "plantuml", "image_svg", "image_png"],
                        },
                        "default": ["exchange_xml"],
                        "description": (
                            "Output formats to return. image_svg / image_png render the diagram "
                            "as a visual and are always accompanied by JSON. Include image_svg "
                            "when the user wants to see the diagram."
                        ),
                    },
                    "compaction": {
                        "type": "string",
                        "enum": ["full", "viewpoint", "abstraction"],
                        "default": "full",
                        "description": "full = complete model; viewpoint = filtered to viewpoint rules; abstraction = maximally compact",
                    },
                    "viewpoint": {
                        "type": "string",
                        "description": "ArchiMate viewpoint name to apply (optional)",
                    },
                    "existing_diagram": {
                        "type": "string",
                        "description": "Existing diagram to refine (any supported format). Requires refinement_query.",
                    },
                    "refinement_query": {
                        "type": "string",
                        "description": "Instruction for refining existing_diagram.",
                    },
                },
            },
        ),
        Tool(
            name="validate_diagram",
            description="Validate an ArchiMate diagram against ArchiMate 3.2 rules.",
            inputSchema={
                "type": "object",
                "required": ["diagram", "format"],
                "properties": {
                    "diagram": {"type": "string", "description": "Diagram content to validate"},
                    "format": {"type": "string", "enum": ["exchange_xml", "json", "mermaid", "plantuml"]},
                    "viewpoint": {"type": "string", "description": "Viewpoint to validate against (optional)"},
                },
            },
        ),
        Tool(
            name="query_spec",
            description="Ask a question about the ArchiMate 3.2 specification.",
            inputSchema={
                "type": "object",
                "required": ["question"],
                "properties": {
                    "question": {"type": "string"},
                    "n_results": {"type": "integer", "default": 5, "description": "Number of spec chunks to retrieve"},
                },
            },
        ),
        Tool(
            name="list_formats",
            description="List supported output formats with descriptions.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    t0 = time.monotonic()
    log.info("[MCP] call_tool ENTER: name=%s", name)
    try:
        session: ServerSession | None = None
        try:
            session = app.request_context.session
            log.debug("[MCP] call_tool: session acquired session_id=%s", id(session))
        except LookupError:
            log.debug("[MCP] call_tool: no session (stdio transport)")

        if name == "generate_diagram":
            log.debug("[MCP] call_tool: dispatching to _tool_generate")
            result = await _tool_generate(arguments, session=session)
            log.info("[MCP] call_tool EXIT: generate_diagram completed in %.2fs", time.monotonic() - t0)
            return result
        if name == "validate_diagram":
            return await _tool_validate(arguments)
        if name == "query_spec":
            return await _tool_query_spec(arguments)
        if name == "list_formats":
            return _tool_list_formats()
        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except BaseException as exc:
        elapsed = time.monotonic() - t0
        log.error("[MCP] call_tool EXCEPTION after %.2fs: %s: %s", elapsed, type(exc).__name__, exc)
        if not isinstance(exc, Exception):
            raise  # re-raise BaseException (CancelledError etc.)
        return [TextContent(type="text", text=f"Error ({type(exc).__name__}): {exc}")]


async def _heartbeat(session: ServerSession, interval: float = 8.0) -> None:
    """Send log notifications while generation runs to keep SSE alive."""
    t_start = time.monotonic()
    n = 0
    while True:
        await asyncio.sleep(interval)
        n += 1
        elapsed = time.monotonic() - t_start
        log.debug("[MCP] heartbeat #%d at t=%.1fs: attempting send_log_message", n, elapsed)
        try:
            await session.send_log_message("info", f"Generating… ({elapsed:.0f}s elapsed)")
            log.debug("[MCP] heartbeat #%d: send_log_message OK", n)
        except asyncio.CancelledError:
            log.debug("[MCP] heartbeat #%d: cancelled (generation done)", n)
            raise
        except Exception as exc:
            log.warning("[MCP] heartbeat #%d at t=%.1fs: FAILED %s: %s", n, elapsed, type(exc).__name__, exc)


async def _tool_generate(args: dict, session: ServerSession | None = None) -> list[TextContent | ImageContent]:
    t0 = time.monotonic()
    log.info("[MCP] _tool_generate START: query=%r session=%s",
             args.get("query", "")[:80], "present" if session else "none")

    requested = args.get("formats", ["exchange_xml"])
    image_formats = [f for f in requested if f in _IMAGE_FORMATS]
    pipeline_formats_raw = [f for f in requested if f not in _IMAGE_FORMATS]

    # Image output requires PlantUML source and JSON result alongside it
    if image_formats:
        if "plantuml" not in pipeline_formats_raw:
            pipeline_formats_raw.append("plantuml")
        if "json" not in pipeline_formats_raw and "exchange_xml" not in pipeline_formats_raw:
            pipeline_formats_raw.append("json")

    formats = [OutputFormat(f) for f in pipeline_formats_raw] if pipeline_formats_raw else [OutputFormat("exchange_xml")]
    compaction = CompactionMode(args.get("compaction", "full"))

    gen_coro = pipeline.generate(
        query=args["query"],
        formats=formats,
        compaction=compaction,
        viewpoint=args.get("viewpoint"),
        existing_diagram=args.get("existing_diagram"),
        refinement_query=args.get("refinement_query"),
        ollama_base_url=settings.ollama_base_url,
        ollama_model=settings.ollama_model,
        ollama_num_ctx=settings.ollama_num_ctx,
        ollama_api_key=settings.ollama_api_key,
    )
    if session is not None:
        log.debug("[MCP] _tool_generate: creating gen_task + heartbeat_task")
        gen_task = asyncio.create_task(gen_coro)
        hb_task = asyncio.create_task(_heartbeat(session))
        try:
            result = await gen_task
            log.info("[MCP] _tool_generate: gen_task DONE in %.2fs", time.monotonic() - t0)
        except BaseException as exc:
            log.error("[MCP] _tool_generate: gen_task FAILED after %.2fs: %s: %s",
                      time.monotonic() - t0, type(exc).__name__, exc)
            raise
        finally:
            log.debug("[MCP] _tool_generate: cancelling heartbeat_task")
            hb_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await hb_task
    else:
        log.debug("[MCP] _tool_generate: no session, awaiting gen_coro directly")
        result = await gen_coro

    response: dict = {
        "model_name": result.model.name,
        "valid": result.validation.valid,
        "violations": [
            {"rule": v.rule, "message": v.message, "severity": v.severity}
            for v in result.validation.violations
        ],
        "compaction": result.compaction_mode.value,
        "outputs": {k: v for k, v in result.outputs.items() if k != "plantuml" or not image_formats},
    }
    if result.compact_validation:
        response["compact_valid"] = result.compact_validation.valid
        response["compact_violations"] = [
            {"rule": v.rule, "message": v.message, "severity": v.severity}
            for v in result.compact_validation.violations
        ]

    contents: list[TextContent | ImageContent] = [
        TextContent(type="text", text=json.dumps(response, indent=2, ensure_ascii=False))
    ]

    plantuml_source = result.outputs.get("plantuml", "")
    for img_fmt in image_formats:
        if not plantuml_source:
            log.warning("[MCP] image format %s requested but no PlantUML output available", img_fmt)
            continue
        fmt_arg = _IMAGE_FMT_ARG[img_fmt]
        mime = _IMAGE_MIME[img_fmt]
        log.debug("[MCP] rendering %s via PlantUML JAR=%s", img_fmt, settings.plantuml_jar)
        try:
            img_bytes = await _render_plantuml(plantuml_source, fmt_arg, settings.plantuml_jar)
            contents.append(ImageContent(
                type="image",
                data=base64.b64encode(img_bytes).decode("ascii"),
                mimeType=mime,
            ))
            log.info("[MCP] %s rendered OK: %d bytes", img_fmt, len(img_bytes))
        except Exception as exc:
            log.error("[MCP] %s render failed: %s", img_fmt, exc)
            contents.append(TextContent(type="text", text=f"[Image render failed: {exc}]"))

    return contents


async def _tool_validate(args: dict) -> list[TextContent]:
    try:
        model = _parse_diagram_input(args["diagram"], args["format"])
        result = val_module.validate(model, viewpoint=args.get("viewpoint"))
        response = {
            "valid": result.valid,
            "violations": [
                {"rule": v.rule, "message": v.message, "severity": v.severity,
                 "element_id": v.element_id, "relationship_id": v.relationship_id}
                for v in result.violations
            ],
        }
    except Exception as exc:
        response = {"valid": False, "error": str(exc), "violations": []}
    return [TextContent(type="text", text=json.dumps(response, indent=2))]


async def _tool_query_spec(args: dict) -> list[TextContent]:
    question = args["question"]
    n = int(args.get("n_results", 5))
    chunks = rag_module.query(question, n_results=n)
    if not chunks:
        text = "No spec index available. Run scripts/bootstrap.py first."
    else:
        text = "\n\n---\n\n".join(chunks)
    return [TextContent(type="text", text=text)]


def _tool_list_formats() -> list[TextContent]:
    formats = {
        "exchange_xml": "Open Group ArchiMate 3 Exchange Format XML. Importable in Archi, BiZZdesign, etc.",
        "json": "Archinator internal JSON schema. Machine-readable, easy to parse.",
        "mermaid": "Mermaid graph diagram. Renderable in GitHub, Notion, many markdown renderers.",
        "plantuml": "PlantUML ArchiMate diagram. Requires ArchiMate PlantUML library.",
    }
    text = "\n".join(f"- **{k}**: {v}" for k, v in formats.items())
    return [TextContent(type="text", text=text)]


def main() -> None:
    logging.basicConfig(level=settings.log_level)
    asyncio.run(_serve())


async def _serve() -> None:
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())


if __name__ == "__main__":
    main()
