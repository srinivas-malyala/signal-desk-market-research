"""M1 production HTTP middleware, session isolation, and pure proposal tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import pytest
import stock_research_mcp_server as server
import yaml
from identity import IdentityError, trusted_embedded_identity, trusted_identity
from pydantic import TypeAdapter, ValidationError
from starlette.testclient import TestClient

from shared.contracts.assistant import NoteArguments, Proposal, ReportArguments

EMBEDDED = "embedded-test-credential-abcdefghijklmnopqrstuvwxyz"
LEGACY = "legacy-test-credential-abcdefghijklmnopqrstuvwxyz"
PROPOSAL_TOOLS = {"propose_watchlist_add", "propose_watchlist_remove", "propose_research_note", "propose_analysis_report"}


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("SIGNAL_DESK_IDENTITY_MODE", "signed_assertion")
    monkeypatch.setenv("MCP_EMBEDDED_ENABLED", "true")
    monkeypatch.setenv("MCP_EMBEDDED_TOKEN", EMBEDDED)
    monkeypatch.setenv("MCP_SUPERVISOR_TOKEN", LEGACY)
    monkeypatch.setenv("MCP_EMBEDDED_SUBJECT", "embedded-test")
    monkeypatch.setenv("MCP_SUPERVISOR_SUBJECT", "legacy-test")
    monkeypatch.setattr(server, "_write_audit", lambda *_args: None)


def rpc(client, path, token, method, params=None, *, session=None, request_id="test-request"):
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json, text/event-stream", "X-Request-ID": request_id}
    if session:
        headers["mcp-session-id"] = session
    return client.post(path, headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}})


def initialize(client, path, token):
    return rpc(client, path, token, "initialize", {
        "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "m1-test", "version": "1"},
    })


def test_real_surfaces_preserve_stateful_legacy_and_stateless_embedded(configured, monkeypatch):
    identities = []

    def performance(*_args):
        identities.append(server._identity.get())
        return {"status": "success", "ticker": "AAPL"}

    monkeypatch.setattr(server.broker, "get_stock_performance", performance)
    with TestClient(server.create_http_app(json_response=True)) as client:
        legacy = initialize(client, "/mcp", LEGACY)
        assert legacy.status_code == 200
        session = legacy.headers["mcp-session-id"]
        tools = rpc(client, "/mcp", LEGACY, "tools/list", session=session).json()["result"]["tools"]
        assert len(tools) == 9
        assert not PROPOSAL_TOOLS & {tool["name"] for tool in tools}
        assert rpc(client, "/mcp", LEGACY, "tools/call", {"name": "get_stock_performance", "arguments": {"ticker": "AAPL"}}, session=session).json()["result"]["isError"] is False
        restricted = initialize(client, "/embedded/mcp", EMBEDDED)
        assert restricted.status_code == 200
        assert "mcp-session-id" not in restricted.headers
        tools = rpc(client, "/embedded/mcp", EMBEDDED, "tools/list").json()["result"]["tools"]
        assert {tool["name"] for tool in tools} == server.EMBEDDED_RESEARCH_TOOLS | PROPOSAL_TOOLS
        assert rpc(client, "/embedded/mcp", EMBEDDED, "tools/call", {"name": "get_stock_performance", "arguments": {"ticker": "AAPL"}}).json()["result"]["isError"] is False
        assert [identity["kind"] for identity in identities] == ["supervisor", "embedded_supervisor"]
        assert client.get("/health").status_code == 200


@pytest.mark.parametrize("path,token", [("/mcp", EMBEDDED), ("/embedded/mcp", LEGACY), ("/embedded/mcp", "wrong")])
def test_cross_surface_credentials_rejected(configured, path, token):
    with TestClient(server.create_http_app(json_response=True)) as client:
        response = initialize(client, path, token)
        assert response.status_code == 401
        assert response.headers.get("x-request-id")


@pytest.mark.parametrize("name", ["update_watchlist", "save_research_note", "save_analysis_report", "get_watchlist", "get_notable_updates"])
def test_forbidden_direct_calls_never_reach_broker(configured, monkeypatch, name):
    forbidden = Mock(side_effect=AssertionError("Forbidden business operation invoked"))
    monkeypatch.setattr(server.broker, name, forbidden)
    with TestClient(server.create_http_app(json_response=True)) as client:
        initialize(client, "/embedded/mcp", EMBEDDED)
        payload = rpc(client, "/embedded/mcp", EMBEDDED, "tools/call", {"name": name, "arguments": {}}).json()
        assert payload.get("error") or payload["result"]["isError"]
        forbidden.assert_not_called()


def test_proposal_is_normalized_nonexecuting_and_has_no_owner(configured, monkeypatch):
    forbidden = Mock(side_effect=AssertionError("No writes from proposal formatter"))
    monkeypatch.setattr(server.broker, "update_watchlist", forbidden)
    monkeypatch.setattr(server.lakebase, "get_connection", forbidden)
    with TestClient(server.create_http_app(json_response=True)) as client:
        initialize(client, "/embedded/mcp", EMBEDDED)
        result = rpc(client, "/embedded/mcp", EMBEDDED, "tools/call", {
            "name": "propose_watchlist_add", "arguments": {"ticker": " nvda "},
        }).json()["result"]["structuredContent"]
        assert result == {"status": "proposal", "executed": False, "proposal": {
            "schema_version": "1", "type": "watchlist_add", "arguments": {"ticker": "NVDA", "watchlist_name": "Primary"},
        }}
        TypeAdapter(Proposal).validate_python(result["proposal"])
        forbidden.assert_not_called()


def test_embedded_context_defense_blocks_even_legacy_wrapper(configured, monkeypatch):
    write = Mock()
    monkeypatch.setattr(server.broker, "update_watchlist", write)
    context = server._identity.set({"kind": "embedded_supervisor"})
    try:
        assert server.update_watchlist.fn("NVDA", "add", confirmed=True)["status"] == "error"
    finally:
        server._identity.reset(context)
    write.assert_not_called()


@pytest.mark.parametrize("setting,value", [
    ("MCP_EMBEDDED_ENABLED", "invalid"), ("MCP_EMBEDDED_TOKEN", "short"),
    ("MCP_EMBEDDED_TOKEN", LEGACY), ("MCP_EMBEDDED_SUBJECT", "legacy-test"),
    ("SIGNAL_DESK_IDENTITY_MODE", "databricks_forwarded"),
])
def test_invalid_enabled_configuration_fails_before_startup(configured, monkeypatch, setting, value):
    monkeypatch.setenv(setting, value)
    with pytest.raises(IdentityError):
        server.create_http_app()


def test_disabled_surface_and_forwarded_bypass_fail_closed(configured, monkeypatch):
    monkeypatch.setenv("MCP_EMBEDDED_ENABLED", "false")
    with pytest.raises(IdentityError):
        trusted_embedded_identity({"authorization": f"Bearer {EMBEDDED}"})
    with TestClient(server.create_http_app(json_response=True)) as client:
        assert initialize(client, "/embedded/mcp", EMBEDDED).status_code == 401
        assert initialize(client, "/mcp", LEGACY).status_code == 200
    monkeypatch.setenv("SIGNAL_DESK_IDENTITY_MODE", "databricks_forwarded")
    with pytest.raises(IdentityError):
        trusted_identity({"authorization": f"Bearer {EMBEDDED}", "x-forwarded-email": "forged@example.com"}, "test-request")


@pytest.mark.parametrize("extra", ["user_email", "confirmed", "idempotency_key", "source_context", "watchlist_name"])
def test_note_proposals_reject_identity_execution_and_unverified_context(extra):
    with pytest.raises(ValidationError):
        NoteArguments.model_validate({"ticker": "AAPL", "title": "Draft", "note_text": "Private text", extra: "forged"})


def test_proposal_content_limits_and_report_tickers():
    with pytest.raises(ValidationError):
        NoteArguments(ticker="AAPL", title="Draft", note_text="x" * 20_001)
    with pytest.raises(ValidationError):
        ReportArguments(title="Draft", tickers=["aapl", "AAPL"], report_text="Draft")
    with pytest.raises(ValidationError):
        NoteArguments(ticker="AAPL", title=" ", note_text="Draft")
    note = NoteArguments(ticker=" aapl ", title=" Draft ", note_text=" Text ", thesis_tags=[" cloud "])
    assert note.model_dump() == {"ticker": "AAPL", "title": "Draft", "note_text": "Text", "thesis_tags": ["cloud"]}


@pytest.mark.parametrize("name,arguments,proposal_type", [
    ("propose_watchlist_remove", {"ticker": "aapl"}, "watchlist_remove"),
    ("propose_research_note", {"ticker": "aapl", "title": "Draft", "note_text": "Text"}, "save_note"),
    ("propose_analysis_report", {"title": "Draft", "tickers": ["aapl", "msft"], "report_text": "Text"}, "save_report"),
])
def test_remaining_formatters_are_valid_and_database_free(configured, monkeypatch, name, arguments, proposal_type):
    forbidden = Mock(side_effect=AssertionError("Proposal must not open a database"))
    monkeypatch.setattr(server.lakebase, "get_connection", forbidden)
    with TestClient(server.create_http_app(json_response=True)) as client:
        result = rpc(client, "/embedded/mcp", EMBEDDED, "tools/call", {
            "name": name, "arguments": arguments,
        }).json()["result"]["structuredContent"]
        assert result["executed"] is False
        proposal = TypeAdapter(Proposal).validate_python(result["proposal"])
        assert proposal.type == proposal_type
    forbidden.assert_not_called()


def test_embedded_spec_matches_tools_and_has_adversarial_examples():
    agent_dir = Path(__file__).resolve().parents[2] / "agent"
    spec = yaml.safe_load((agent_dir / "embedded_agent_config.yaml").read_text())
    assert set(spec["external_mcp_connection"]["tools"]) == server.EMBEDDED_RESEARCH_TOOLS | PROPOSAL_TOOLS
    assert spec["deployment"]["status"] == "not_provisioned"
    assert spec["deployment"]["serving_endpoint"] is None
    assert (agent_dir / spec["supervisor"]["instructions_file"]).is_file()
    examples = json.loads((agent_dir / spec["evaluation"]["fixture_file"]).read_text())
    assert set(examples["forbidden_tools"]) == set(spec["external_mcp_connection"]["forbidden_tools"])
    assert len(examples["examples"]) >= 10
    assert all(example["question"] and example["guidelines"] for example in examples["examples"])
