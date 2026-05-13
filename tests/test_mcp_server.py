"""MCP server handler tests — no Ollama or ChromaDB required."""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend", "src"))

import pytest

pytestmark = pytest.mark.asyncio

from unittest.mock import AsyncMock, patch
from mcp.types import TextContent

from archinator.server import list_tools, call_tool, _tool_generate, _tool_validate, _tool_query_spec, _tool_list_formats
from archinator.models import (
    ArchiMateModel, GenerationResult, ValidationResult, ValidationViolation,
    CompactionMode, OutputFormat,
)


VALID_MODEL_JSON = json.dumps({
    "id": "t1", "name": "Test", "views": [],
    "elements": [{"id": "e1", "type": "BusinessProcess", "name": "P",
                  "layer": "Business", "aspect": "Behavior"}],
    "relationships": [],
})

INVALID_ELEMENT_JSON = json.dumps({
    "id": "t2", "name": "Bad", "views": [],
    "elements": [{"id": "e1", "type": "MagicBox", "name": "M",
                  "layer": "Business", "aspect": "Behavior"}],
    "relationships": [],
})


def _gen_result(valid=True, outputs=None, compaction=CompactionMode.FULL):
    return GenerationResult(
        model=ArchiMateModel(id="m1", name="Test"),
        validation=ValidationResult(valid=valid),
        outputs=outputs or {"exchange_xml": "<model/>"},
        compaction_mode=compaction,
    )


# ---------------------------------------------------------------------------
# list_tools
# ---------------------------------------------------------------------------

async def test_list_tools_returns_four_tools():
    tools = await list_tools()
    assert len(tools) == 4


async def test_list_tools_names():
    tools = await list_tools()
    names = {t.name for t in tools}
    assert names == {"generate_diagram", "validate_diagram", "query_spec", "list_formats"}


async def test_list_tools_generate_diagram_requires_query():
    tools = await list_tools()
    gen = next(t for t in tools if t.name == "generate_diagram")
    assert "query" in gen.inputSchema["required"]


async def test_list_tools_validate_diagram_requires_diagram_and_format():
    tools = await list_tools()
    val = next(t for t in tools if t.name == "validate_diagram")
    assert set(val.inputSchema["required"]) == {"diagram", "format"}


async def test_list_tools_list_formats_has_no_required():
    tools = await list_tools()
    lf = next(t for t in tools if t.name == "list_formats")
    assert lf.inputSchema.get("required", []) == []


# ---------------------------------------------------------------------------
# _tool_list_formats
# ---------------------------------------------------------------------------

async def test_list_formats_returns_text_content():
    result = _tool_list_formats()
    assert len(result) == 1
    assert isinstance(result[0], TextContent)
    assert result[0].type == "text"


async def test_list_formats_contains_all_four_formats():
    text = _tool_list_formats()[0].text
    for fmt in ("exchange_xml", "json", "mermaid", "plantuml"):
        assert fmt in text


# ---------------------------------------------------------------------------
# _tool_validate
# ---------------------------------------------------------------------------

async def test_validate_valid_json_returns_valid_true():
    result = await _tool_validate({"diagram": VALID_MODEL_JSON, "format": "json"})
    data = json.loads(result[0].text)
    assert data["valid"] is True
    assert data["violations"] == []


async def test_validate_invalid_element_type_returns_violation():
    result = await _tool_validate({"diagram": INVALID_ELEMENT_JSON, "format": "json"})
    data = json.loads(result[0].text)
    assert data["valid"] is False
    assert any(v["rule"] == "element_type_legality" for v in data["violations"])


async def test_validate_unsupported_parse_format_returns_error():
    result = await _tool_validate({"diagram": "graph LR\nA-->B", "format": "mermaid"})
    data = json.loads(result[0].text)
    assert data["valid"] is False
    assert "error" in data


async def test_validate_malformed_json_returns_error():
    result = await _tool_validate({"diagram": "not json", "format": "json"})
    data = json.loads(result[0].text)
    assert data["valid"] is False
    assert "error" in data


async def test_validate_returns_single_text_content():
    result = await _tool_validate({"diagram": VALID_MODEL_JSON, "format": "json"})
    assert len(result) == 1
    assert isinstance(result[0], TextContent)


async def test_validate_violations_include_expected_fields():
    result = await _tool_validate({"diagram": INVALID_ELEMENT_JSON, "format": "json"})
    data = json.loads(result[0].text)
    v = data["violations"][0]
    assert "rule" in v
    assert "message" in v
    assert "severity" in v


# ---------------------------------------------------------------------------
# _tool_query_spec
# ---------------------------------------------------------------------------

async def test_query_spec_chunks_joined_with_separator():
    chunks = ["Section A", "Section B"]
    with patch("archinator.server.rag_module.query", return_value=chunks):
        result = await _tool_query_spec({"question": "What is Composition?"})
    text = result[0].text
    assert "Section A" in text
    assert "Section B" in text
    assert "---" in text


async def test_query_spec_empty_returns_bootstrap_message():
    with patch("archinator.server.rag_module.query", return_value=[]):
        result = await _tool_query_spec({"question": "anything"})
    assert "bootstrap" in result[0].text.lower() or "No spec index" in result[0].text


async def test_query_spec_default_n_results_is_five():
    with patch("archinator.server.rag_module.query", return_value=[]) as mock_q:
        await _tool_query_spec({"question": "test"})
    mock_q.assert_called_once_with("test", n_results=5)


async def test_query_spec_custom_n_results_forwarded():
    with patch("archinator.server.rag_module.query", return_value=[]) as mock_q:
        await _tool_query_spec({"question": "test", "n_results": 3})
    mock_q.assert_called_once_with("test", n_results=3)


# ---------------------------------------------------------------------------
# _tool_generate
# ---------------------------------------------------------------------------

async def test_generate_response_has_required_keys():
    with patch("archinator.server.pipeline.generate", new=AsyncMock(return_value=_gen_result())):
        result = await _tool_generate({"query": "a business process"})
    data = json.loads(result[0].text)
    for key in ("model_name", "valid", "violations", "compaction", "outputs"):
        assert key in data


async def test_generate_default_format_is_exchange_xml():
    with patch("archinator.server.pipeline.generate", new=AsyncMock(return_value=_gen_result())) as mock_gen:
        await _tool_generate({"query": "test"})
    kwargs = mock_gen.call_args.kwargs
    assert [f.value for f in kwargs["formats"]] == ["exchange_xml"]


async def test_generate_default_compaction_is_full():
    with patch("archinator.server.pipeline.generate", new=AsyncMock(return_value=_gen_result())) as mock_gen:
        await _tool_generate({"query": "test"})
    kwargs = mock_gen.call_args.kwargs
    assert kwargs["compaction"].value == "full"


async def test_generate_explicit_formats_and_compaction_forwarded():
    with patch("archinator.server.pipeline.generate", new=AsyncMock(return_value=_gen_result())) as mock_gen:
        await _tool_generate({
            "query": "test",
            "formats": ["json", "mermaid"],
            "compaction": "viewpoint",
            "viewpoint": "BusinessProcess",
        })
    kwargs = mock_gen.call_args.kwargs
    assert {f.value for f in kwargs["formats"]} == {"json", "mermaid"}
    assert kwargs["compaction"].value == "viewpoint"
    assert kwargs["viewpoint"] == "BusinessProcess"


async def test_generate_compact_validation_included_when_set():
    result = _gen_result()
    result.compact_validation = ValidationResult(
        valid=False,
        violations=[ValidationViolation(rule="test_rule", message="msg")],
    )
    with patch("archinator.server.pipeline.generate", new=AsyncMock(return_value=result)):
        out = await _tool_generate({"query": "test"})
    data = json.loads(out[0].text)
    assert data["compact_valid"] is False
    assert any(v["rule"] == "test_rule" for v in data["compact_violations"])


async def test_generate_no_compact_validation_keys_absent():
    with patch("archinator.server.pipeline.generate", new=AsyncMock(return_value=_gen_result())):
        out = await _tool_generate({"query": "test"})
    data = json.loads(out[0].text)
    assert "compact_valid" not in data
    assert "compact_violations" not in data


# ---------------------------------------------------------------------------
# call_tool dispatcher
# ---------------------------------------------------------------------------

async def test_call_tool_routes_list_formats():
    result = await call_tool("list_formats", {})
    assert any("exchange_xml" in r.text for r in result)


async def test_call_tool_unknown_tool_returns_error():
    result = await call_tool("nonexistent_tool", {})
    assert len(result) == 1
    assert "Unknown tool" in result[0].text
    assert "nonexistent_tool" in result[0].text


async def test_call_tool_routes_validate_diagram():
    result = await call_tool("validate_diagram", {"diagram": VALID_MODEL_JSON, "format": "json"})
    data = json.loads(result[0].text)
    assert "valid" in data


async def test_call_tool_routes_query_spec():
    with patch("archinator.server.rag_module.query", return_value=[]):
        result = await call_tool("query_spec", {"question": "test"})
    assert isinstance(result[0], TextContent)


async def test_call_tool_routes_generate_diagram():
    with patch("archinator.server.pipeline.generate", new=AsyncMock(return_value=_gen_result())):
        result = await call_tool("generate_diagram", {"query": "test"})
    data = json.loads(result[0].text)
    assert "valid" in data


# ---------------------------------------------------------------------------
# Subprocess smoke test (optional — requires entry point installed)
# ---------------------------------------------------------------------------

@pytest.mark.integration
async def test_subprocess_initialize_and_list_tools():
    import asyncio

    def _frame(obj: dict) -> bytes:
        body = json.dumps(obj).encode()
        return b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body

    async def _read_msg(reader) -> dict:
        header = b""
        while not header.endswith(b"\r\n\r\n"):
            header += await reader.read(1)
        length = int(header.split(b"Content-Length: ")[1].split(b"\r\n")[0])
        body = await reader.readexactly(length)
        return json.loads(body)

    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "archinator.server",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=os.path.join(os.path.dirname(__file__), "..", "backend"),
    )
    try:
        proc.stdin.write(_frame({
            "jsonrpc": "2.0", "id": 0, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0.0.1"},
            },
        }))
        await proc.stdin.drain()
        init_resp = await asyncio.wait_for(_read_msg(proc.stdout), timeout=10.0)
        assert init_resp["id"] == 0
        assert "result" in init_resp

        proc.stdin.write(_frame({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}))
        await proc.stdin.drain()

        proc.stdin.write(_frame({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}))
        await proc.stdin.drain()
        tools_resp = await asyncio.wait_for(_read_msg(proc.stdout), timeout=10.0)
        assert tools_resp["id"] == 1
        names = {t["name"] for t in tools_resp["result"]["tools"]}
        assert names == {"generate_diagram", "validate_diagram", "query_spec", "list_formats"}
    finally:
        proc.terminate()
        await proc.wait()
