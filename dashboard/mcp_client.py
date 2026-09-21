"""Bounded synchronous abstraction over the Signal Desk FastMCP service."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlparse

from fastmcp import Client

MAX_TOOL_RESPONSE_BYTES = 256_000


class MCPClientError(RuntimeError):
    """Base class for safe frontend-facing MCP failures."""


class MCPConfigurationError(MCPClientError):
    """The frontend has no valid MCP service configuration."""


class MCPUnavailableError(MCPClientError):
    """The MCP service could not be reached or returned an invalid response."""


class MCPToolError(MCPClientError):
    """The MCP tool rejected a valid frontend request."""


class WatchlistClient(Protocol):
    def update_watchlist(
        self,
        *,
        ticker: str,
        action: str,
        access_token: str,
        request_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]: ...


def _payload(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if not isinstance(structured, dict):
        structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict):
        payload = structured
    else:
        payload = None
        for block in getattr(result, "content", []) or []:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    payload = parsed
                    break
        if payload is None:
            raise MCPUnavailableError("The research service returned an invalid response.")
    if len(json.dumps(payload, default=str).encode("utf-8")) > MAX_TOOL_RESPONSE_BYTES:
        raise MCPUnavailableError("The research service response exceeded the allowed size.")
    if payload.get("status") == "error":
        message = str(payload.get("message") or "The research action was rejected.")
        raise MCPToolError(message[:500])
    return payload


@dataclass(frozen=True)
class FastMCPWatchlistClient:
    endpoint: str
    timeout_seconds: int = 20

    @classmethod
    def from_environment(cls) -> FastMCPWatchlistClient:
        raw_url = os.getenv("MCP_SERVER_URL", "").strip().rstrip("/")
        parsed = urlparse(raw_url)
        is_local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        valid_scheme = parsed.scheme in ({"https"} if not is_local else {"http", "https"})
        if (
            not raw_url
            or not valid_scheme
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise MCPConfigurationError("The research service is not configured.")
        try:
            timeout = int(os.getenv("MCP_TIMEOUT_SECONDS", "20"))
        except ValueError as exc:
            raise MCPConfigurationError("The research service timeout is invalid.") from exc
        if timeout < 1 or timeout > 60:
            raise MCPConfigurationError("The research service timeout is invalid.")
        endpoint = raw_url if raw_url.endswith("/mcp") else f"{raw_url}/mcp"
        return cls(endpoint=endpoint, timeout_seconds=timeout)

    async def _call(
        self,
        name: str,
        arguments: dict[str, Any],
        access_token: str,
        request_id: str,
    ) -> dict[str, Any]:
        try:
            async with Client(self.endpoint, auth=access_token, timeout=self.timeout_seconds) as client:
                result = await client.call_tool_mcp(
                    name,
                    arguments,
                    timeout=self.timeout_seconds,
                    meta={"frontend_request_id": request_id},
                )
            return _payload(result)
        except MCPClientError:
            raise
        except Exception as exc:
            raise MCPUnavailableError("The research service is temporarily unavailable.") from exc

    def update_watchlist(
        self,
        *,
        ticker: str,
        action: str,
        access_token: str,
        request_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return asyncio.run(
            self._call(
                "update_watchlist",
                {
                    "ticker": ticker,
                    "action": action,
                    "watchlist_name": "Primary",
                    "confirmed": True,
                    "idempotency_key": idempotency_key,
                },
                access_token,
                request_id,
            )
        )
