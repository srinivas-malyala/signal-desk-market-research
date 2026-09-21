from __future__ import annotations

import importlib.util
import sys
import uuid
from pathlib import Path
from unittest.mock import Mock

import pytest

pytest.importorskip("flask")

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_ROOT = ROOT / "dashboard"
AUTH_HEADERS = {
    "X-Forwarded-Email": "student@example.com",
    "X-Forwarded-Access-Token": "trusted-user-token",
}


@pytest.fixture
def app_module(monkeypatch: pytest.MonkeyPatch):
    fake_db = Mock()
    fake_db.write.return_value = {"id": 1}
    fake_db.query.return_value = []
    fake_db.table_name.side_effect = lambda base: f"bootcamp_students.{base}_srini"
    fake_mcp = Mock()
    fake_mcp.update_watchlist.return_value = {
        "status": "success",
        "ticker": "AAPL",
        "action": "add",
        "idempotent_replay": False,
    }
    fake_mcp.get_stock_performance.return_value = {"status": "success", "ticker": "AAPL", "as_of": "2026-09-09"}
    fake_mcp.compare_stocks.return_value = {"status": "success", "comparisons": []}
    fake_mcp.semantic_research.return_value = {"status": "success", "results": []}
    fake_mcp.get_company_research.return_value = {"status": "success", "ticker": "AAPL"}
    monkeypatch.setitem(sys.modules, "lakebase", fake_db)
    monkeypatch.syspath_prepend(str(DASHBOARD_ROOT))
    spec = importlib.util.spec_from_file_location("dashboard_app", DASHBOARD_ROOT / "app.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.app.config.update(TESTING=True, MCP_CLIENT_FACTORY=lambda: fake_mcp)
    module.test_mcp = fake_mcp
    return module


def test_health_route_is_public_but_hardened(app_module) -> None:
    response = app_module.app.test_client().get("/healthz")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "service": "signal-desk-frontend",
        "contract_version": "1.0",
    }
    uuid.UUID(response.headers["X-Request-ID"])
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"X-Forwarded-Email": "student@example.com"},
        {"X-Forwarded-Access-Token": "trusted-user-token"},
        {"X-Forwarded-Email": "not-an-email", "X-Forwarded-Access-Token": "trusted-user-token"},
    ],
)
def test_user_routes_fail_closed_without_complete_trusted_identity(app_module, headers: dict) -> None:
    response = app_module.app.test_client().get("/api/overview", headers=headers)

    assert response.status_code == 401
    payload = response.get_json()
    assert payload["error_code"] == "authentication_required"
    assert payload["request_id"] == response.headers["X-Request-ID"]
    assert "demo@example.com" not in response.get_data(as_text=True)
    app_module.lakebase.query.assert_not_called()
    app_module.lakebase.write.assert_not_called()


def test_identity_in_request_body_is_never_authoritative(app_module) -> None:
    response = app_module.app.test_client().post(
        "/api/watchlist",
        json={"ticker": "AAPL", "user_email": "attacker@example.com"},
    )

    assert response.status_code == 401
    app_module.test_mcp.update_watchlist.assert_not_called()


def test_dashboard_template_escapes_forwarded_identity(app_module) -> None:
    response = app_module.app.test_client().get(
        "/",
        headers={
            "X-Forwarded-Email": "student&researcher@example.com",
            "X-Forwarded-Access-Token": "trusted-user-token",
        },
    )

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "student&amp;researcher@example.com" in page
    assert "student&researcher@example.com" not in page


def test_existing_watchlist_validation_does_not_call_mcp(app_module) -> None:
    response = app_module.app.test_client().post(
        "/api/watchlist",
        json={"ticker": "not valid"},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 400
    assert response.get_json()["error_code"] == "invalid_ticker"
    app_module.test_mcp.update_watchlist.assert_not_called()


def test_oversized_request_is_rejected_before_mcp(app_module) -> None:
    response = app_module.app.test_client().post(
        "/api/watchlist",
        data='{"ticker":"' + ("A" * 40_000) + '"}',
        content_type="application/json",
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 413
    assert response.get_json()["error_code"] == "payload_too_large"
    app_module.test_mcp.update_watchlist.assert_not_called()


def test_watchlist_add_uses_mcp_user_token_request_id_and_idempotency(app_module) -> None:
    headers = {**AUTH_HEADERS, "Idempotency-Key": "frontend-request-123"}
    response = app_module.app.test_client().post("/api/watchlist", json={"ticker": "aapl"}, headers=headers)

    assert response.status_code == 201
    request_id = response.headers["X-Request-ID"]
    assert response.get_json()["request_id"] == request_id
    app_module.test_mcp.update_watchlist.assert_called_once_with(
        ticker="AAPL",
        action="add",
        access_token="trusted-user-token",
        request_id=request_id,
        idempotency_key="frontend-request-123",
    )
    app_module.lakebase.write.assert_not_called()


def test_watchlist_remove_uses_mcp_and_rejects_bad_idempotency_key(app_module) -> None:
    bad = app_module.app.test_client().delete(
        "/api/watchlist/AAPL",
        headers={**AUTH_HEADERS, "Idempotency-Key": "short"},
    )
    assert bad.status_code == 400
    app_module.test_mcp.update_watchlist.assert_not_called()

    response = app_module.app.test_client().delete(
        "/api/watchlist/aapl",
        headers={**AUTH_HEADERS, "Idempotency-Key": "frontend-remove-123"},
    )
    assert response.status_code == 200
    app_module.test_mcp.update_watchlist.assert_called_once_with(
        ticker="AAPL",
        action="remove",
        access_token="trusted-user-token",
        request_id=response.headers["X-Request-ID"],
        idempotency_key="frontend-remove-123",
    )


def test_mcp_dependency_failure_is_safe_and_correlated(app_module) -> None:
    app_module.test_mcp.update_watchlist.side_effect = app_module.MCPUnavailableError(
        "internal-host.example.test failed"
    )
    response = app_module.app.test_client().post(
        "/api/watchlist",
        json={"ticker": "AAPL"},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 502
    payload = response.get_json()
    assert payload["error_code"] == "mcp_unavailable"
    assert payload["request_id"] == response.headers["X-Request-ID"]
    assert "internal-host" not in response.get_data(as_text=True)


def test_research_performance_uses_authenticated_mcp_contract(app_module) -> None:
    response = app_module.app.test_client().post(
        "/api/research",
        json={"mode": "performance", "ticker": "aapl", "lookback_days": 30},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["execution_identity"] == "authenticated user"
    app_module.test_mcp.get_stock_performance.assert_called_once_with(
        ticker="AAPL",
        lookback_days=30,
        access_token="trusted-user-token",
        request_id=response.headers["X-Request-ID"],
    )


def test_research_comparison_validates_bounds_before_mcp(app_module) -> None:
    invalid = app_module.app.test_client().post(
        "/api/research",
        json={"mode": "comparison", "tickers": ["AAPL"], "lookback_days": 30},
        headers=AUTH_HEADERS,
    )
    assert invalid.status_code == 400
    app_module.test_mcp.compare_stocks.assert_not_called()

    response = app_module.app.test_client().post(
        "/api/research",
        json={"mode": "comparison", "tickers": ["aapl", "msft"], "lookback_days": 60},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    app_module.test_mcp.compare_stocks.assert_called_once_with(
        tickers=["AAPL", "MSFT"],
        lookback_days=60,
        access_token="trusted-user-token",
        request_id=response.headers["X-Request-ID"],
    )


def test_evidence_research_returns_sources_and_optional_company_context(app_module) -> None:
    response = app_module.app.test_client().post(
        "/api/research",
        json={
            "mode": "evidence",
            "query": "What filing evidence supports services growth?",
            "tickers": ["AAPL"],
            "source_types": ["filing"],
        },
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["evidence"]["status"] == "success"
    assert payload["company"]["ticker"] == "AAPL"
    app_module.test_mcp.semantic_research.assert_called_once()
    app_module.test_mcp.get_company_research.assert_called_once_with(
        ticker="AAPL",
        access_token="trusted-user-token",
        request_id=response.headers["X-Request-ID"],
    )


def test_research_rate_limit_has_distinct_http_state(app_module) -> None:
    app_module.test_mcp.get_stock_performance.side_effect = app_module.MCPToolError(
        "The Massive API rate limit was reached.", "massive_http_429"
    )
    response = app_module.app.test_client().post(
        "/api/research",
        json={"mode": "performance", "ticker": "AAPL", "lookback_days": 30},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 429
    assert response.get_json()["error_code"] == "massive_http_429"


def test_dashboard_sql_uses_student_suffixed_tables(app_module) -> None:
    response = app_module.app.test_client().get("/api/overview", headers=AUTH_HEADERS)

    assert response.status_code == 200
    statements = [call.args[0] for call in app_module.lakebase.query.call_args_list]
    statements += [call.args[0] for call in app_module.lakebase.write.call_args_list]
    assert statements
    assert all("bootcamp_students." in statement for statement in statements)
    assert all("_srini" in statement for statement in statements)


def test_demo_identity_and_direct_watchlist_writes_are_removed() -> None:
    source = (DASHBOARD_ROOT / "app.py").read_text(encoding="utf-8")

    assert "demo@example.com" not in source
    assert "X-Forwarded-Email" in source
    assert "X-Forwarded-Access-Token" in source
    watchlist_routes = source[source.index('@app.post("/api/watchlist")') :]
    assert "lakebase.write(" not in watchlist_routes
