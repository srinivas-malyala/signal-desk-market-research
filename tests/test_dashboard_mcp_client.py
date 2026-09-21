from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).parents[1]
DASHBOARD_ROOT = ROOT / "dashboard"
SPEC = importlib.util.spec_from_file_location("dashboard_mcp_client", DASHBOARD_ROOT / "mcp_client.py")
assert SPEC and SPEC.loader
MCP_CLIENT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MCP_CLIENT
SPEC.loader.exec_module(MCP_CLIENT)
FastMCPWatchlistClient = MCP_CLIENT.FastMCPWatchlistClient
MCPConfigurationError = MCP_CLIENT.MCPConfigurationError
MCPToolError = MCP_CLIENT.MCPToolError
MCPUnavailableError = MCP_CLIENT.MCPUnavailableError
_payload = MCP_CLIENT._payload


def test_mcp_endpoint_configuration_fails_closed_and_requires_tls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MCP_SERVER_URL", raising=False)
    with pytest.raises(MCPConfigurationError):
        FastMCPWatchlistClient.from_environment()

    monkeypatch.setenv("MCP_SERVER_URL", "http://mcp.example.test")
    with pytest.raises(MCPConfigurationError):
        FastMCPWatchlistClient.from_environment()

    monkeypatch.setenv("MCP_SERVER_URL", "https://mcp.example.test")
    client = FastMCPWatchlistClient.from_environment()
    assert client.endpoint == "https://mcp.example.test/mcp"

    monkeypatch.setenv("MCP_TIMEOUT_SECONDS", "not-a-number")
    with pytest.raises(MCPConfigurationError, match="timeout"):
        FastMCPWatchlistClient.from_environment()
    monkeypatch.delenv("MCP_TIMEOUT_SECONDS")

    monkeypatch.setenv("MCP_SERVER_URL", "http://localhost:8001/mcp")
    assert FastMCPWatchlistClient.from_environment().endpoint == "http://localhost:8001/mcp"


def test_mcp_payload_accepts_structured_results_and_rejects_errors_and_oversize() -> None:
    assert _payload(SimpleNamespace(structuredContent={"status": "success", "ticker": "AAPL"})) == {
        "status": "success",
        "ticker": "AAPL",
    }
    with pytest.raises(MCPToolError, match="already present"):
        _payload(SimpleNamespace(structuredContent={"status": "error", "message": "Ticker already present"}))
    with pytest.raises(MCPToolError) as bounded_error:
        _payload(SimpleNamespace(structuredContent={"status": "error", "message": "x" * 5_000}))
    assert len(str(bounded_error.value)) == 500
    with pytest.raises(MCPUnavailableError, match="exceeded"):
        _payload(SimpleNamespace(structuredContent={"status": "success", "value": "x" * 256_001}))


def test_watchlist_client_builds_confirmed_bounded_tool_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    async def fake_call(self, name, arguments, access_token, request_id):
        captured.update(
            {
                "name": name,
                "arguments": arguments,
                "access_token": access_token,
                "request_id": request_id,
            }
        )
        return {"status": "success", "ticker": arguments["ticker"]}

    monkeypatch.setattr(FastMCPWatchlistClient, "_call", fake_call)
    client = FastMCPWatchlistClient("https://mcp.example.test/mcp")
    result = client.update_watchlist(
        ticker="AAPL",
        action="add",
        access_token="user-token",
        request_id="request-123",
        idempotency_key="frontend-request-123",
    )

    assert result == {"status": "success", "ticker": "AAPL"}
    assert captured == {
        "name": "update_watchlist",
        "arguments": {
            "ticker": "AAPL",
            "action": "add",
            "watchlist_name": "Primary",
            "confirmed": True,
            "idempotency_key": "frontend-request-123",
        },
        "access_token": "user-token",
        "request_id": "request-123",
    }


def test_research_methods_align_with_final_mcp_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    async def fake_call(self, name, arguments, access_token, request_id):
        calls.append((name, arguments, access_token, request_id))
        return {"status": "success"}

    monkeypatch.setattr(FastMCPWatchlistClient, "_call", fake_call)
    client = FastMCPWatchlistClient("https://mcp.example.test/mcp")
    client.get_stock_performance(ticker="AAPL", lookback_days=30, access_token="token", request_id="req")
    client.compare_stocks(tickers=["AAPL", "MSFT"], lookback_days=60, access_token="token", request_id="req")
    client.semantic_research(
        query="services growth",
        tickers=["AAPL"],
        source_types=["filing"],
        start_date=None,
        end_date=None,
        access_token="token",
        request_id="req",
    )
    client.get_company_research(ticker="AAPL", access_token="token", request_id="req")
    assert [call[0] for call in calls] == [
        "get_stock_performance",
        "compare_stocks",
        "semantic_research",
        "get_company_research",
    ]
    assert calls[2][1]["top_k"] == 5
    assert calls[3][1]["include_fundamentals"] is True


def test_saved_research_methods_are_confirmed_and_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    async def fake_call(self, name, arguments, access_token, request_id):
        calls.append((name, arguments))
        return {"status": "success"}
    monkeypatch.setattr(FastMCPWatchlistClient, "_call", fake_call)
    client = FastMCPWatchlistClient("https://mcp.example.test/mcp")
    client.save_research_note(ticker="AAPL", title="Thesis", note_text="Text", thesis_tags=[], access_token="token", request_id="req", idempotency_key="note-key-123")
    client.save_analysis_report(title="Report", thesis="Thesis", tickers=["AAPL"], report_text="Text", source_context={}, access_token="token", request_id="req", idempotency_key="report-key-123")
    assert [call[0] for call in calls] == ["save_research_note", "save_analysis_report"]
    assert all(call[1]["confirmed"] is True for call in calls)
    assert [call[1]["idempotency_key"] for call in calls] == ["note-key-123", "report-key-123"]


def test_mcp_client_never_forges_forwarded_identity_headers() -> None:
    source = (DASHBOARD_ROOT / "mcp_client.py").read_text(encoding="utf-8").lower()
    assert "x-forwarded-email" not in source
    assert "x-forwarded-user" not in source
    assert "x-forwarded-access-token" not in source
