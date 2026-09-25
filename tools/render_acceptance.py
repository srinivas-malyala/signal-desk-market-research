#!/usr/bin/env python3
"""Sanitized health and security preflight for the two deployed Render services."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

SECURITY_HEADERS = (
    "cache-control",
    "content-security-policy",
    "permissions-policy",
    "referrer-policy",
    "strict-transport-security",
    "x-content-type-options",
    "x-frame-options",
    "x-request-id",
)


def _base_url(value: str, label: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{label} must be a safe HTTPS service URL")
    return value.rstrip("/")


def run_checks(
    mcp_url: str,
    frontend_url: str,
    *,
    timeout_seconds: int = 30,
    get: Callable[..., Any] = requests.get,
    post: Callable[..., Any] = requests.post,
) -> dict[str, Any]:
    mcp = _base_url(mcp_url, "MCP URL")
    frontend = _base_url(frontend_url, "Frontend URL")
    checks: list[dict[str, Any]] = []

    mcp_health = get(f"{mcp}/health", timeout=timeout_seconds)
    checks.append(
        {
            "name": "mcp_public_health",
            "passed": mcp_health.status_code == 200
            and mcp_health.json().get("service") == "stock-market-research",
            "status_code": mcp_health.status_code,
        }
    )
    unauthorized = post(f"{mcp}/mcp", timeout=timeout_seconds)
    checks.append(
        {
            "name": "mcp_requires_identity",
            "passed": unauthorized.status_code == 401,
            "status_code": unauthorized.status_code,
        }
    )

    frontend_health = get(f"{frontend}/healthz", timeout=timeout_seconds)
    missing_headers = sorted(name for name in SECURITY_HEADERS if not frontend_health.headers.get(name))
    checks.append(
        {
            "name": "frontend_public_health_and_headers",
            "passed": frontend_health.status_code == 200
            and frontend_health.json().get("service") == "signal-desk-frontend"
            and not missing_headers,
            "status_code": frontend_health.status_code,
            "missing_headers": missing_headers,
        }
    )
    unauthenticated_api = get(f"{frontend}/api/overview", timeout=timeout_seconds, allow_redirects=False)
    payload = unauthenticated_api.json() if unauthenticated_api.headers.get("content-type", "").startswith("application/json") else {}
    checks.append(
        {
            "name": "frontend_api_fails_closed",
            "passed": unauthenticated_api.status_code == 401
            and payload.get("error_code") == "authentication_required",
            "status_code": unauthenticated_api.status_code,
        }
    )
    browser = get(frontend, timeout=timeout_seconds, allow_redirects=False)
    checks.append(
        {
            "name": "frontend_browser_starts_oidc",
            "passed": browser.status_code in {302, 303}
            and str(browser.headers.get("location") or "").endswith("/login"),
            "status_code": browser.status_code,
        }
    )
    return {
        "status": "passed" if all(check["passed"] for check in checks) else "failed",
        "mcp_host": urlparse(mcp).hostname,
        "frontend_host": urlparse(frontend).hostname,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mcp-url", required=True)
    parser.add_argument("--frontend-url", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_checks(args.mcp_url, args.frontend_url, timeout_seconds=args.timeout_seconds)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
    print(rendered)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
