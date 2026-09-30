#!/usr/bin/env python3
"""Run a sanitized read-only Render MCP market-backend canary check."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


def _payload(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict):
        return structured
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            value = json.loads(text)
            if isinstance(value, dict):
                return value
    raise RuntimeError("MCP tool did not return structured JSON")


async def check(url: str, token: str, ticker: str, lookback_days: int, timeout: int) -> dict:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("MCP URL must be HTTPS without embedded credentials")
    if len(token) < 32 or any(character.isspace() for character in token):
        raise ValueError("MCP machine credential is invalid")
    base_url = url.rstrip("/")
    health = requests.get(f"{base_url}/health", timeout=timeout)
    health.raise_for_status()
    transport = StreamableHttpTransport(f"{base_url}/mcp", auth=token)
    async with Client(transport, timeout=timeout) as client:
        tools = {str(tool.name) for tool in await client.list_tools()}
        performance = _payload(
            await client.call_tool_mcp(
                "get_stock_performance",
                {"ticker": ticker, "lookback_days": lookback_days},
            )
        )
    bars = performance.get("daily_bars")
    bars = bars if isinstance(bars, list) else []
    source = str(performance.get("source") or "")
    checks = {
        "health": health.status_code == 200 and health.json().get("status") == "ok",
        "tool_present": "get_stock_performance" in tools,
        "tool_success": performance.get("status") == "success",
        "ticker": performance.get("ticker") == ticker,
        "bounded_rows": 0 < len(bars) <= 370,
        "lakebase_source": source.startswith("Lakebase published market history serving table"),
        "as_of_present": bool(performance.get("as_of")),
    }
    return {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "ticker": performance.get("ticker"),
        "as_of": performance.get("as_of"),
        "row_count": len(bars),
        "source": source,
        "correlation_id": performance.get("correlation_id"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--bearer-file", type=Path, required=True)
    parser.add_argument("--ticker", default="AAPL")
    parser.add_argument("--lookback-days", type=int, default=30)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = asyncio.run(
        check(
            args.url,
            args.bearer_file.read_text(encoding="utf-8").strip(),
            args.ticker.strip().upper(),
            args.lookback_days,
            args.timeout_seconds,
        )
    )
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
    print(rendered)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
