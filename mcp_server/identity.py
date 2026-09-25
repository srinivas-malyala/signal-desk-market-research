"""Trusted identity providers for Databricks proxy and Render bearer traffic."""

from __future__ import annotations

import hmac
import os
import re
import time
from collections.abc import Mapping

import jwt

SUBJECT = re.compile(r"^[A-Za-z0-9._:@/-]{1,255}$")


class IdentityError(ValueError):
    """A request did not carry a valid trusted identity."""


def identity_mode() -> str:
    mode = os.getenv("SIGNAL_DESK_IDENTITY_MODE", "databricks_forwarded").strip().casefold()
    if mode not in {"databricks_forwarded", "signed_assertion"}:
        raise IdentityError("The identity mode is invalid.")
    return mode


def _bearer(headers: Mapping[str, str]) -> str:
    authorization = str(headers.get("authorization") or "")
    scheme, separator, credential = authorization.partition(" ")
    if separator != " " or scheme.casefold() != "bearer" or not credential or any(c.isspace() for c in credential):
        raise IdentityError("A bearer credential is required.")
    return credential


def _supervisor_identity(token: str) -> dict | None:
    expected = os.getenv("MCP_SUPERVISOR_TOKEN", "").strip()
    if len(expected) < 32 or not hmac.compare_digest(token, expected):
        return None
    subject = os.getenv("MCP_SUPERVISOR_SUBJECT", "signal-desk-supervisor").strip()
    if not SUBJECT.fullmatch(subject):
        raise IdentityError("The Supervisor subject is invalid.")
    return {
        "email": f"{subject}@service.signal-desk.invalid",
        "subject": subject,
        "access_token": None,
        "kind": "supervisor",
    }


def _frontend_identity(token: str, request_id: str) -> dict:
    public_key = os.getenv("FRONTEND_ASSERTION_PUBLIC_KEY", "").strip().replace("\\n", "\n")
    if len(public_key) < 64:
        raise IdentityError("The frontend verification key is not configured.")
    issuer = os.getenv("FRONTEND_ASSERTION_ISSUER", "signal-desk-frontend").strip()
    audience = os.getenv("FRONTEND_ASSERTION_AUDIENCE", "signal-desk-mcp").strip()
    try:
        claims = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
            leeway=5,
            options={"require": ["exp", "iat", "iss", "aud", "sub", "email", "jti", "rid"]},
        )
    except Exception as exc:
        raise IdentityError("The frontend identity assertion is invalid.") from exc
    issued = int(claims["iat"])
    expires = int(claims["exp"])
    if expires - issued > 60 or issued > int(time.time()) + 5:
        raise IdentityError("The frontend identity assertion lifetime is invalid.")
    email = str(claims.get("email") or "").strip().lower()
    subject = str(claims.get("sub") or "").strip()
    token_request_id = str(claims.get("rid") or "")
    if "@" not in email or len(email) > 320 or not SUBJECT.fullmatch(subject):
        raise IdentityError("The frontend identity claims are invalid.")
    if not request_id or not hmac.compare_digest(token_request_id, request_id):
        raise IdentityError("The frontend identity request binding is invalid.")
    return {"email": email, "subject": subject, "access_token": None, "kind": "frontend"}


def trusted_identity(headers: Mapping[str, str], request_id: str) -> dict:
    if identity_mode() == "databricks_forwarded":
        return {
            "email": headers.get("x-forwarded-email") or headers.get("x-forwarded-user"),
            "access_token": headers.get("x-forwarded-access-token"),
            "kind": "databricks_user",
        }
    token = _bearer(headers)
    return _supervisor_identity(token) or _frontend_identity(token, request_id)
