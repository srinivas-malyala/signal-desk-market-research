"""Local design spike: real installed MCP transport, no database or external API."""

from __future__ import annotations

import asyncio
import json
from contextlib import AsyncExitStack, asynccontextmanager

import httpx
import pytest
from fastmcp import Client, FastMCP
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.exceptions import ToolError
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Mount

from tools.assistant_m0_probe import MAX_EVENT_BYTES, RESEARCH_TOOLS, sse_events, summarize


def test_capture_metadata_does_not_expose_text_or_argument_values():
    events = [
        {"type": "response.output_item.done", "item": {
            "id": "call-1", "type": "function_call", "name": "service__semantic_research",
            "arguments": json.dumps({"query": "private thesis", "tickers": ["AAPL"], "source_types": ["filing"]}),
        }},
        {"type": "response.output_item.done", "item": {
            "id": "message-1", "type": "message", "role": "assistant",
            "content": [{"type": "output_text", "text": "private response"}],
        }},
        {"type": "response.completed", "response": {"status": "completed", "output": []}},
    ]
    lines = [line for event in events for line in (f"data: {json.dumps(event)}", "")]
    result = summarize(sse_events(lines))
    assert result["terminal_state"] == "completed"
    assert result["tool_calls"][0]["argument_types"]["tickers"] == "list"
    assert "private" not in json.dumps(result)
    assert "AAPL" not in json.dumps(result)


@pytest.mark.parametrize("terminal", [None, "response.failed", "response.incomplete"])
def test_partial_text_does_not_imply_success(terminal):
    events = [{"type": "response.output_item.done", "item": {"type": "message", "role": "assistant", "content": []}}]
    if terminal:
        events.append({"type": terminal})
    assert summarize(events)["terminal_state"] == ("failed" if terminal else "interrupted")


def test_sse_multiline_crlf_and_done():
    lines = [":heartbeat\r\n", 'data: {"type":\r\n', 'data: "response.completed"}\r\n', "\r\n", "data: [DONE]\r\n"]
    assert summarize(sse_events(lines))["terminal_state"] == "completed"


def test_oversized_event_and_nonobject_rejected():
    with pytest.raises(ValueError, match="event_limit"):
        list(sse_events(["data: " + "x" * (MAX_EVENT_BYTES + 1)]))
    with pytest.raises(ValueError, match="invalid_event"):
        list(sse_events(["data: []", ""]))


def test_completed_items_are_not_double_counted():
    item = {"id": "message-1", "type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "answer"}]}
    result = summarize([
        {"type": "response.output_item.done", "item": item},
        {"type": "response.completed", "response": {"status": "completed", "output": [item]}},
    ])
    assert result["assistant_text_lengths"] == [6]


def test_call_and_output_with_same_id_are_distinct():
    result = summarize([
        {"type": "response.output_item.done", "item": {"id": "shared", "type": "function_call", "name": "compare_stocks", "arguments": {}}},
        {"type": "response.output_item.done", "item": {"id": "shared", "type": "function_call_output", "output": "private data"}},
    ])
    assert result["item_types"] == {"function_call": 1, "function_call_output": 1}
    assert result["tool_calls"][0]["research_allowlisted"] is True


def test_transport_done_is_recorded_without_inventing_response_completion():
    result = summarize(sse_events(["data: [DONE]"]))
    assert result["event_types"] == {"transport.done": 1}
    assert result["terminal_state"] == "interrupted"


def test_done_after_final_assistant_item_is_verified_completion():
    result = summarize([
        {"type": "response.output_item.done", "item": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "answer"}]}},
        {"type": "transport.done"},
    ])
    assert result["terminal_state"] == "completed"


@pytest.mark.parametrize("text,valid", [
    ('{"schema_version":"1","answer":"Draft only","proposals":[]}', True),
    ('{"schema_version":"1","answer":"Draft only","proposals":[],"user_email":"forged"}', False),
    ('```json\n{}\n```', False),
])
def test_envelope_shape_probe_is_strict(text, valid):
    result = summarize([{"type": "response.output_item.done", "item": {
        "type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}],
    }}])
    assert result["envelope_shapes"] == [valid]


def test_separate_http_mounts_restrict_discovery_and_direct_calls():
    async def exercise():
        restricted = FastMCP("m0-restricted")
        legacy = FastMCP("m0-legacy")
        calls = []

        for name in RESEARCH_TOOLS:
            def research(ticker: str = "AAPL") -> dict:
                return {"status": "success", "ticker": ticker}
            restricted.tool(research, name=name)
            legacy.tool(research, name=name)

        @legacy.tool
        def update_watchlist(ticker: str) -> dict:
            calls.append(ticker)
            return {"status": "success"}

        # A proposal formatter has no database or mutation capability.
        @restricted.tool
        def propose_watchlist(ticker: str) -> dict:
            return {"schema_version": "1", "type": "watchlist_add", "arguments": {"ticker": ticker, "watchlist_name": "Primary"}}

        class CredentialBoundary(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                wanted = "Bearer embedded-test" if request.url.path.startswith("/embedded/") else "Bearer legacy-test"
                if request.headers.get("authorization") != wanted:
                    return JSONResponse({"error": "authentication_required"}, status_code=401)
                return await call_next(request)

        apps = [restricted.http_app(path="/mcp", stateless_http=True, json_response=True),
                legacy.http_app(path="/mcp", stateless_http=True, json_response=True)]

        @asynccontextmanager
        async def lifespan(_app):
            async with AsyncExitStack() as stack:
                for child in apps:
                    await stack.enter_async_context(child.router.lifespan_context(child))
                yield

        parent = Starlette(routes=[Mount("/embedded", app=apps[0]), Mount("/legacy", app=apps[1])],
                           middleware=[Middleware(CredentialBoundary)], lifespan=lifespan)

        def factory(**kwargs):
            return httpx.AsyncClient(transport=httpx.ASGITransport(app=parent), **kwargs)

        async with parent.router.lifespan_context(parent):
            transport = StreamableHttpTransport("http://m0/embedded/mcp", auth="embedded-test", httpx_client_factory=factory)
            async with Client(transport) as client:
                names = {tool.name for tool in await client.list_tools()}
                assert names == RESEARCH_TOOLS | {"propose_watchlist"}
                proposal = await client.call_tool("propose_watchlist", {"ticker": "NVDA"})
                assert proposal.structured_content["type"] == "watchlist_add"
                for name in ("update_watchlist", "save_research_note", "save_analysis_report", "get_watchlist", "get_notable_updates"):
                    with pytest.raises(ToolError):
                        await client.call_tool(name, {})
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=parent)) as http:
                denied = await http.post("http://m0/legacy/mcp", headers={"Authorization": "Bearer embedded-test"})
                assert denied.status_code == 401
            transport = StreamableHttpTransport("http://m0/legacy/mcp", auth="legacy-test", httpx_client_factory=factory)
            async with Client(transport) as client:
                await client.call_tool("update_watchlist", {"ticker": "NVDA"})
            assert calls == ["NVDA"]

    asyncio.run(exercise())
