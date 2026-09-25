from __future__ import annotations

import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from flask import Flask, session

from dashboard import auth as frontend_auth
from mcp_server import identity as mcp_identity


@pytest.fixture(scope="module")
def signing_keys() -> tuple[str, str]:
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
    return private_pem, public_pem


def _configure_render(monkeypatch: pytest.MonkeyPatch, signing_keys: tuple[str, str]) -> None:
    private_pem, public_pem = signing_keys
    monkeypatch.setenv("SIGNAL_DESK_HOSTING", "render")
    monkeypatch.setenv("SIGNAL_DESK_IDENTITY_MODE", "signed_assertion")
    monkeypatch.setenv("FRONTEND_ASSERTION_PRIVATE_KEY", private_pem)
    monkeypatch.setenv("FRONTEND_ASSERTION_PUBLIC_KEY", public_pem)
    monkeypatch.setenv("FRONTEND_ASSERTION_ISSUER", "signal-desk-frontend")
    monkeypatch.setenv("FRONTEND_ASSERTION_AUDIENCE", "signal-desk-mcp")


def test_frontend_assertion_round_trip_is_request_bound(
    monkeypatch: pytest.MonkeyPatch,
    signing_keys: tuple[str, str],
) -> None:
    _configure_render(monkeypatch, signing_keys)
    app = Flask(__name__)
    app.secret_key = "test-secret-that-is-long-enough-for-session-signing"
    with app.test_request_context("/"):
        session["user_email"] = "student@example.com"
        session["user_subject"] = "oidc-subject-123"
        frontend = frontend_auth.trusted_identity("request-123")

    resolved = mcp_identity.trusted_identity(
        {"authorization": f"Bearer {frontend.mcp_access_token}"},
        "request-123",
    )
    assert resolved == {
        "email": "student@example.com",
        "subject": "oidc-subject-123",
        "access_token": None,
        "kind": "frontend",
        "token_id": resolved["token_id"],
        "expires_at": resolved["expires_at"],
    }
    with pytest.raises(mcp_identity.IdentityError, match="request binding"):
        mcp_identity.trusted_identity(
            {"authorization": f"Bearer {frontend.mcp_access_token}"},
            "different-request",
        )


def test_expired_and_tampered_assertions_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    signing_keys: tuple[str, str],
) -> None:
    _configure_render(monkeypatch, signing_keys)
    private_pem, _public_pem = signing_keys
    now = int(time.time())
    expired = jwt.encode(
        {
            "iss": "signal-desk-frontend",
            "aud": "signal-desk-mcp",
            "sub": "student-123",
            "email": "student@example.com",
            "iat": now - 120,
            "exp": now - 60,
            "jti": "expired-token-id",
            "rid": "request-123",
        },
        private_pem,
        algorithm="RS256",
    )
    with pytest.raises(mcp_identity.IdentityError, match="invalid"):
        mcp_identity.trusted_identity({"authorization": f"Bearer {expired}"}, "request-123")
    with pytest.raises(mcp_identity.IdentityError, match="invalid"):
        mcp_identity.trusted_identity({"authorization": f"Bearer {expired}tampered"}, "request-123")


def test_supervisor_uses_fixed_server_side_identity(
    monkeypatch: pytest.MonkeyPatch,
    signing_keys: tuple[str, str],
) -> None:
    _configure_render(monkeypatch, signing_keys)
    token = "supervisor-machine-credential-with-at-least-32-characters"
    monkeypatch.setenv("MCP_SUPERVISOR_TOKEN", token)
    monkeypatch.setenv("MCP_SUPERVISOR_SUBJECT", "capstone-supervisor")
    assert mcp_identity.trusted_identity({"authorization": f"Bearer {token}"}, "request-1") == {
        "email": "capstone-supervisor@service.signal-desk.invalid",
        "subject": "capstone-supervisor",
        "access_token": None,
        "kind": "supervisor",
    }


def test_render_csrf_requires_the_session_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIGNAL_DESK_HOSTING", "render")
    app = Flask(__name__)
    app.secret_key = "test-secret-that-is-long-enough-for-session-signing"
    with app.test_request_context("/api/watchlist", method="POST", headers={"X-CSRF-Token": "wrong"}):
        session["csrf_token"] = "correct-token-that-is-longer-than-32-characters"
        assert frontend_auth.csrf_is_valid() is False
    with app.test_request_context(
        "/api/watchlist",
        method="POST",
        headers={"X-CSRF-Token": "correct-token-that-is-longer-than-32-characters"},
    ):
        session["csrf_token"] = "correct-token-that-is-longer-than-32-characters"
        assert frontend_auth.csrf_is_valid() is True


def test_forwarded_headers_are_ignored_in_render_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIGNAL_DESK_HOSTING", "render")
    app = Flask(__name__)
    app.secret_key = "test-secret-that-is-long-enough-for-session-signing"
    with app.test_request_context(
        "/",
        headers={
            "X-Forwarded-Email": "attacker@example.com",
            "X-Forwarded-Access-Token": "attacker-token",
        },
    ):
        with pytest.raises(ValueError, match="missing identity"):
            frontend_auth.trusted_identity("request-123")


def test_frontend_assertion_cannot_initialize_a_second_mcp_session() -> None:
    identity = {
        "kind": "frontend",
        "token_id": "one-time-jti",
        "expires_at": 2_000,
    }
    mcp_identity._assertion_sessions.clear()
    mcp_identity.reserve_assertion_session(identity, None, now=1_000)
    mcp_identity.bind_assertion_session(identity, "session-one")
    mcp_identity.reserve_assertion_session(identity, "session-one", now=1_001)
    with pytest.raises(mcp_identity.IdentityError, match="replayed"):
        mcp_identity.reserve_assertion_session(identity, None, now=1_001)
    with pytest.raises(mcp_identity.IdentityError, match="replayed"):
        mcp_identity.reserve_assertion_session(identity, "session-two", now=1_001)
