"""Frontend authentication, CSRF, and Render-to-MCP identity assertions."""

from __future__ import annotations

import hmac
import os
import secrets
import time
import uuid
from dataclasses import dataclass
from urllib.parse import urlparse

import jwt
from authlib.integrations.flask_client import OAuth
from flask import Flask, redirect, request, session, url_for

EMAIL_LIMIT = 320
oauth = OAuth()


class FrontendAuthConfigurationError(RuntimeError):
    """The deployed authentication boundary is not configured safely."""


@dataclass(frozen=True)
class FrontendIdentity:
    email: str
    subject: str
    mcp_access_token: str


def hosting_mode() -> str:
    mode = os.getenv("SIGNAL_DESK_HOSTING", "databricks").strip().casefold()
    if mode not in {"databricks", "local", "render"}:
        raise FrontendAuthConfigurationError("SIGNAL_DESK_HOSTING is invalid.")
    return mode


def _required(name: str, *, minimum: int = 1, maximum: int = 16_384) -> str:
    value = os.getenv(name, "").strip()
    if not minimum <= len(value) <= maximum:
        raise FrontendAuthConfigurationError(f"{name} is not configured.")
    return value


def _https_url(name: str) -> str:
    value = _required(name, maximum=2_048)
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise FrontendAuthConfigurationError(f"{name} must be a safe HTTPS URL.")
    return value


def configure_frontend_auth(app: Flask) -> None:
    if hosting_mode() != "render":
        return
    app.secret_key = _required("FLASK_SESSION_SECRET", minimum=32, maximum=4_096)
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=3600,
    )
    issuer = _https_url("OIDC_ISSUER_URL").rstrip("/")
    oauth.init_app(app)
    oauth.register(
        name="signal_desk_oidc",
        server_metadata_url=f"{issuer}/.well-known/openid-configuration",
        client_id=_required("OIDC_CLIENT_ID", minimum=3, maximum=512),
        client_secret=_required("OIDC_CLIENT_SECRET", minimum=8, maximum=4_096),
        client_kwargs={"scope": "openid email profile"},
    )


def register_auth_routes(app: Flask) -> None:
    @app.get("/login")
    def login():
        if hosting_mode() != "render":
            return redirect(url_for("index"))
        nonce = secrets.token_urlsafe(32)
        session.clear()
        session["oidc_nonce"] = nonce
        return oauth.signal_desk_oidc.authorize_redirect(_https_url("OIDC_REDIRECT_URI"), nonce=nonce)

    @app.get("/oidc/callback")
    def oidc_callback():
        if hosting_mode() != "render":
            return redirect(url_for("index"))
        nonce = session.pop("oidc_nonce", None)
        if not nonce:
            raise FrontendAuthConfigurationError("OIDC login state is missing.")
        token = oauth.signal_desk_oidc.authorize_access_token()
        claims = oauth.signal_desk_oidc.parse_id_token(token, nonce=nonce)
        email = str(claims.get("email") or "").strip().lower()
        subject = str(claims.get("sub") or "").strip()
        if not claims.get("email_verified") or "@" not in email or len(email) > EMAIL_LIMIT:
            raise FrontendAuthConfigurationError("OIDC did not return a verified email.")
        if not 1 <= len(subject) <= 255:
            raise FrontendAuthConfigurationError("OIDC did not return a valid subject.")
        allowed = {
            item.strip().lower()
            for item in os.getenv("ALLOWED_USER_EMAILS", "").split(",")
            if item.strip()
        }
        if allowed and email not in allowed:
            session.clear()
            return ("This account is not authorized for Signal Desk.", 403)
        session.clear()
        session.permanent = True
        session["user_email"] = email
        session["user_subject"] = subject
        session["csrf_token"] = secrets.token_urlsafe(32)
        return redirect(url_for("index"))

    @app.post("/logout")
    def logout():
        if hosting_mode() == "render" and not csrf_is_valid():
            return ("CSRF validation failed.", 403)
        session.clear()
        return redirect(url_for("login" if hosting_mode() == "render" else "index"))


def csrf_token() -> str:
    if hosting_mode() != "render":
        return ""
    token = str(session.get("csrf_token") or "")
    if len(token) < 32:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def csrf_is_valid() -> bool:
    if hosting_mode() != "render" or request.method in {"GET", "HEAD", "OPTIONS"}:
        return True
    expected = str(session.get("csrf_token") or "")
    supplied = str(request.headers.get("X-CSRF-Token") or request.form.get("csrf_token") or "")
    return len(expected) >= 32 and hmac.compare_digest(expected, supplied)


def _assertion(email: str, subject: str, request_id: str) -> str:
    private_key = _required("FRONTEND_ASSERTION_PRIVATE_KEY", minimum=64, maximum=32_768).replace("\\n", "\n")
    now = int(time.time())
    claims = {
        "iss": os.getenv("FRONTEND_ASSERTION_ISSUER", "signal-desk-frontend").strip(),
        "aud": os.getenv("FRONTEND_ASSERTION_AUDIENCE", "signal-desk-mcp").strip(),
        "sub": subject,
        "email": email,
        "iat": now,
        "exp": now + 60,
        "jti": str(uuid.uuid4()),
        "rid": request_id,
    }
    if not claims["iss"] or not claims["aud"]:
        raise FrontendAuthConfigurationError("Frontend assertion issuer or audience is invalid.")
    try:
        return jwt.encode(claims, private_key, algorithm="RS256")
    except Exception as exc:
        raise FrontendAuthConfigurationError("Frontend assertion signing is unavailable.") from exc


def trusted_identity(request_id: str) -> FrontendIdentity:
    if hosting_mode() == "render":
        email = str(session.get("user_email") or "").strip().lower()
        subject = str(session.get("user_subject") or "").strip()
        if "@" not in email or len(email) > EMAIL_LIMIT or not 1 <= len(subject) <= 255:
            raise ValueError("missing identity")
        return FrontendIdentity(email, subject, _assertion(email, subject, request_id))

    email = str(request.headers.get("X-Forwarded-Email") or "").strip().lower()
    token = str(request.headers.get("X-Forwarded-Access-Token") or "").strip()
    if "@" not in email or len(email) > EMAIL_LIMIT:
        raise ValueError("missing identity")
    if len(token) < 8 or len(token) > 16_384 or any(character.isspace() for character in token):
        raise ValueError("missing access token")
    return FrontendIdentity(email, email, token)
