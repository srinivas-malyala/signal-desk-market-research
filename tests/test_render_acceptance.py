from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from tools.render_acceptance import SECURITY_HEADERS, run_checks


@dataclass
class Response:
    status_code: int
    payload: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)

    def json(self) -> dict[str, Any]:
        return self.payload


def test_render_preflight_checks_health_auth_redirect_and_security_headers() -> None:
    def get(url: str, **_kwargs):
        if url.endswith("/health"):
            return Response(200, {"service": "stock-market-research"})
        if url.endswith("/healthz"):
            return Response(
                200,
                {"service": "signal-desk-frontend"},
                {name: "present" for name in SECURITY_HEADERS},
            )
        if url.endswith("/api/overview"):
            return Response(
                401,
                {"error_code": "authentication_required"},
                {"content-type": "application/json"},
            )
        return Response(302, headers={"location": "/login"})

    report = run_checks(
        "https://signal-desk-mcp.onrender.com",
        "https://signal-desk-frontend.onrender.com",
        get=get,
        post=lambda *_args, **_kwargs: Response(401),
    )
    assert report["status"] == "passed"
    assert all(check["passed"] for check in report["checks"])


@pytest.mark.parametrize(
    "url",
    ("http://service.example.test", "https://user:pass@service.example.test", "https://service.example.test?q=secret"),
)
def test_render_preflight_rejects_unsafe_service_urls(url: str) -> None:
    with pytest.raises(ValueError, match="safe HTTPS"):
        run_checks(url, "https://frontend.example.test")
