from __future__ import annotations

import json
import logging
from datetime import datetime

import pytest
import stock_research_mcp_server as server
from audit import pseudonymous_subject, result_summary, safe_parameters, trusted_email


def test_forwarded_identity_is_required_for_user_owned_tools() -> None:
    with pytest.raises(ValueError, match="trusted user"):
        trusted_email(None)
    assert trusted_email({"email": " Person@Example.com "}) == "person@example.com"
    assert pseudonymous_subject("Person@Example.com") == pseudonymous_subject(" person@example.com ")
    assert "person@example.com" not in str(pseudonymous_subject("person@example.com"))


def test_trace_metadata_excludes_bodies_tokens_and_oversized_results() -> None:
    parameters = safe_parameters(
        {
            "ticker": "AAPL",
            "note_text": "secret thesis" * 100,
            "report_text": "private report" * 100,
            "source_context": {"raw": "private evidence"},
            "idempotency_key": "request-sensitive-123",
        }
    )
    serialized = repr(parameters)
    assert "secret thesis" not in serialized
    assert "private report" not in serialized
    assert "private evidence" not in serialized
    assert "request-sensitive-123" not in serialized
    assert parameters["note_text"]["characters"] == 1300

    result = result_summary(
        {"status": "success", "ticker": "AAPL", "daily_bars": [{"close": number} for number in range(500)]}
    )
    assert result == {
        "status": "success",
        "ticker": "AAPL",
        "collection_counts": {"daily_bars": 500},
    }


def test_dependency_auth_failure_log_is_searchable_and_sanitized(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "must-not-appear-in-render"
    monkeypatch.setattr(server, "_write_audit", lambda *_args, **_kwargs: None)

    @server.traced
    def semantic_lookup() -> dict:
        return {
            "status": "error",
            "error_code": "invalid_request",
            "message": f"invalid_client: Client authentication failed; client_secret={secret}",
        }

    caplog.set_level(logging.INFO, logger="signal_desk.mcp")
    token = server._correlation.set("request-safe-123")
    try:
        result = semantic_lookup()
    finally:
        server._correlation.reset(token)

    record = caplog.records[-1]
    event = json.loads(record.getMessage())
    assert result["message"].endswith(secret)
    assert record.levelno == logging.WARNING
    assert event == {
        "correlation_id": "request-safe-123",
        "dependency_error_code": "invalid_client",
        "duration_ms": event["duration_ms"],
        "error_code": "invalid_request",
        "error_type": "dependency_authentication",
        "event": "mcp_tool_completed",
        "status": "error",
        "timestamp": event["timestamp"],
        "tool": "semantic_lookup",
    }
    assert event["duration_ms"] >= 0
    assert datetime.fromisoformat(event["timestamp"]).tzinfo is not None
    assert secret not in record.getMessage()
    assert "client_secret" not in record.getMessage()
    assert "Client authentication failed" not in record.getMessage()


def test_non_allowlisted_failure_never_logs_raw_message(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "bearer-token-must-not-appear"
    monkeypatch.setattr(server, "_write_audit", lambda *_args, **_kwargs: None)

    @server.traced
    def failed_tool() -> dict:
        return {
            "status": "error",
            "error_code": "unsafe\ncode",
            "message": f"unexpected dependency response {secret}",
        }

    caplog.set_level(logging.INFO, logger="signal_desk.mcp")
    failed_tool()

    event = json.loads(caplog.records[-1].getMessage())
    assert event["error_code"] == "unknown_error"
    assert event["error_type"] == "tool_error"
    assert "dependency_error_code" not in event
    assert secret not in caplog.records[-1].getMessage()
