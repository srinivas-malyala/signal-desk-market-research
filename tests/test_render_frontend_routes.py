from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import Mock

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

pytest.importorskip("flask")

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_ROOT = ROOT / "dashboard"
BASE_URL = "https://localhost"


@pytest.fixture
def render_app(monkeypatch: pytest.MonkeyPatch):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    settings = {
        "SIGNAL_DESK_HOSTING": "render",
        "SIGNAL_DESK_IDENTITY_MODE": "oidc_session",
        "FLASK_SESSION_SECRET": "render-test-session-secret-that-is-long-enough",
        "OIDC_ISSUER_URL": "https://accounts.example.test",
        "OIDC_CLIENT_ID": "render-client-id",
        "OIDC_CLIENT_SECRET": "render-client-secret-value",
        "OIDC_REDIRECT_URI": f"{BASE_URL}/oidc/callback",
        "FRONTEND_ASSERTION_PRIVATE_KEY": private_pem,
        "FRONTEND_ASSERTION_ISSUER": "signal-desk-frontend",
        "FRONTEND_ASSERTION_AUDIENCE": "signal-desk-mcp",
    }
    for name, value in settings.items():
        monkeypatch.setenv(name, value)

    fake_db = Mock()
    fake_db.query.return_value = []
    fake_db.table_name.side_effect = lambda base: f"bootcamp_students.{base}_srini"
    fake_mcp = Mock()
    fake_mcp.update_watchlist.return_value = {
        "status": "success",
        "ticker": "AAPL",
        "action": "add",
    }
    fake_analytics = Mock()
    monkeypatch.setitem(sys.modules, "lakebase", fake_db)
    monkeypatch.syspath_prepend(str(DASHBOARD_ROOT))
    sys.modules.pop("auth", None)
    spec = importlib.util.spec_from_file_location("render_dashboard_app", DASHBOARD_ROOT / "app.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.app.config.update(
        TESTING=True,
        MCP_CLIENT_FACTORY=lambda: fake_mcp,
        ANALYTICS_CLIENT_FACTORY=lambda: fake_analytics,
    )
    module.test_mcp = fake_mcp
    module.test_public_key = public_pem
    return module


def _sign_in(client) -> None:
    with client.session_transaction() as session:
        session["user_email"] = "student@example.com"
        session["user_subject"] = "oidc-subject-123"
        session["csrf_token"] = "csrf-token-that-is-definitely-longer-than-32-characters"


def test_render_browser_redirects_to_login_and_api_fails_closed(render_app) -> None:
    client = render_app.app.test_client()
    browser = client.get("/", base_url=BASE_URL)
    assert browser.status_code == 302
    assert browser.headers["Location"].endswith("/login")
    api = client.get("/api/overview", base_url=BASE_URL)
    assert api.status_code == 401
    assert api.get_json()["error_code"] == "authentication_required"


def test_render_write_requires_csrf_and_sends_verified_signed_identity(render_app) -> None:
    client = render_app.app.test_client()
    _sign_in(client)
    rejected = client.post(
        "/api/watchlist",
        base_url=BASE_URL,
        json={"ticker": "AAPL"},
        headers={"Idempotency-Key": "render-write-123"},
    )
    assert rejected.status_code == 403
    assert rejected.get_json()["error_code"] == "csrf_failed"
    render_app.test_mcp.update_watchlist.assert_not_called()

    accepted = client.post(
        "/api/watchlist",
        base_url=BASE_URL,
        json={"ticker": "AAPL"},
        headers={
            "Idempotency-Key": "render-write-123",
            "X-CSRF-Token": "csrf-token-that-is-definitely-longer-than-32-characters",
        },
    )
    assert accepted.status_code == 201
    call = render_app.test_mcp.update_watchlist.call_args.kwargs
    claims = jwt.decode(
        call["access_token"],
        render_app.test_public_key,
        algorithms=["RS256"],
        audience="signal-desk-mcp",
        issuer="signal-desk-frontend",
    )
    assert claims["email"] == "student@example.com"
    assert claims["sub"] == "oidc-subject-123"
    assert claims["rid"] == accepted.headers["X-Request-ID"]
    assert claims["exp"] - claims["iat"] == 60
