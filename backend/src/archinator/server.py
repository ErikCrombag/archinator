"""MCP server — stdio transport."""
from __future__ import annotations
import asyncio
import contextlib
import json
import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.session import ServerSession
from mcp.types import Tool, TextContent

from .config import settings
from .models import CompactionMode, OutputFormat
from .generation import pipeline
from .validation import validator as val_module
from .validation.rules import VIEWPOINTS
from .knowledge import rag as rag_module
from . import _parse_diagram_input

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
                        "items": {"type": "string", "enum": ["exchange_xml", "json", "mermaid", "plantuml"]},
                        "default": ["exchange_xml"],
                        "description": "Output formats to return",
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
    try:
        session: ServerSession | None = None
        try:
            session = app.request_context.session
        except LookupError:
            pass  # stdio transport — no session context

        if name == "generate_diagram":
            return await _tool_generate(arguments, session=session)
        if name == "validate_diagram":
            return await _tool_validate(arguments)
        if name == "query_spec":
            return await _tool_query_spec(arguments)
        if name == "list_formats":
            return _tool_list_formats()
        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as exc:
        log.exception("Tool %s failed: %s", name, exc)
        return [TextContent(type="text", text=f"Error ({type(exc).__name__}): {exc}")]


async def _heartbeat(session: ServerSession, interval: float = 8.0) -> None:
    """Send log notifications while generation runs to keep SSE alive."""
    messages = [
        "Retrieving ArchiMate spec context…",
        "Generating diagram…",
        "Model still working…",
        "Validating and formatting…",
    ]
    for msg in messages:
        await asyncio.sleep(interval)
        with contextlib.suppress(Exception):
            await session.send_log_message("info", msg)


async def _tool_generate(args: dict, session: ServerSession | None = None) -> list[TextContent]:
    formats = [OutputFormat(f) for f in args.get("formats", ["exchange_xml"])]
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
        gen_task = asyncio.create_task(gen_coro)
        hb_task = asyncio.create_task(_heartbeat(session))
        try:
            result = await gen_task
        finally:
            hb_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await hb_task
    else:
        result = await gen_coro
    response: dict = {
        "model_name": result.model.name,
        "valid": result.validation.valid,
        "violations": [
            {"rule": v.rule, "message": v.message, "severity": v.severity}
            for v in result.validation.violations
        ],
        "compaction": result.compaction_mode.value,
        "outputs": result.outputs,
    }
    if result.compact_validation:
        response["compact_valid"] = result.compact_validation.valid
        response["compact_violations"] = [
            {"rule": v.rule, "message": v.message, "severity": v.severity}
            for v in result.compact_validation.violations
        ]
    return [TextContent(type="text", text=json.dumps(response, indent=2, ensure_ascii=False))]


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
