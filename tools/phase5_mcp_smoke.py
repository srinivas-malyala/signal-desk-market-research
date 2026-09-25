#!/usr/bin/env python3
"""Post-deployment MCP health, retrieval, optional action, and trace smoke test."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from databricks.sdk import WorkspaceClient

ROOT = Path(__file__).resolve().parents[1]
MCP_ROOT = ROOT / "mcp_server"
EXPECTED_TOOLS = {
    "get_stock_performance",
    "get_company_research",
    "compare_stocks",
    "get_watchlist",
    "update_watchlist",
    "save_research_note",
    "save_analysis_report",
    "semantic_research",
    "get_notable_updates",
}
WRITE_TEST_TICKERS = ("SPY", "QQQ", "DIA", "IWM")


def _safe_failure_detail(payload: dict[str, Any]) -> str:
    """Return bounded, server-sanitized failure metadata for acceptance reports."""
    if payload.get("status") != "error":
        return ""
    error_code = str(payload.get("error_code") or "unknown_error")[:100]
    message = " ".join(str(payload.get("message") or "No safe error message returned.").split())[:300]
    return f", error_code={error_code}, message={message}"


def _tool_payload(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict):
        return structured
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
    raise RuntimeError("MCP tool did not return a structured JSON object")


def _correlation_id(payload: dict[str, Any]) -> str:
    value = str(payload.get("correlation_id") or "")
    if not value:
        raise RuntimeError("MCP tool response omitted correlation_id")
    return value


def _choose_disposable_ticker(watchlist: dict[str, Any]) -> str:
    present = {
        str(item.get("ticker") or "").upper()
        for item in watchlist.get("tickers", [])
        if isinstance(item, dict)
    }
    for ticker in WRITE_TEST_TICKERS:
        if ticker not in present:
            return ticker
    raise RuntimeError("No disposable acceptance ticker is available")


def _trace_evidence(correlation_ids: list[str]) -> dict[str, Any]:
    if str(MCP_ROOT) not in sys.path:
        sys.path.insert(0, str(MCP_ROOT))
    import lakebase

    trace_table = lakebase.table_name("stock_research_mcp_traces")
    event_table = lakebase.table_name("agent_tool_events")
    traces = lakebase.query(
        f"""SELECT tool_name,status,result->>'correlation_id' AS correlation_id,
        coalesce(jsonb_typeof(tool_parameters->'idempotency_key'),'missing') AS idempotency_shape,
        CASE
          WHEN tool_parameters->'idempotency_key' IS NULL THEN true
          WHEN jsonb_typeof(tool_parameters->'idempotency_key') = 'object' THEN NOT EXISTS (
            SELECT 1
            FROM jsonb_object_keys(tool_parameters->'idempotency_key') AS keys(key_name)
            WHERE key_name NOT IN ('provided','characters')
          )
          ELSE false
        END AS idempotency_redacted,
        length(tool_parameters::text) AS parameter_bytes,
        length(result::text) AS result_bytes
        FROM {trace_table}
        WHERE result->>'correlation_id'=ANY(%s)""",
        (correlation_ids,),
    )
    events = lakebase.query(
        f"""SELECT tool_name,status,metadata->'result'->>'correlation_id' AS correlation_id,
        length(metadata::text) AS metadata_bytes
        FROM {event_table}
        WHERE metadata->'result'->>'correlation_id'=ANY(%s)""",
        (correlation_ids,),
    )
    return {
        "trace_count": len(traces),
        "event_count": len(events),
        "trace_correlation_ids": sorted(row["correlation_id"] for row in traces),
        "event_correlation_ids": sorted(row["correlation_id"] for row in events),
        "trace_payloads_bounded": all(
            int(row.get("parameter_bytes") or 0) <= 4096
            and int(row.get("result_bytes") or 0) <= 4096
            for row in traces
        ),
        "idempotency_values_redacted": all(
            row.get("idempotency_shape") in {"missing", "object"}
            and row.get("idempotency_redacted") is True
            for row in traces
        ),
        "event_payloads_bounded": all(int(row.get("metadata_bytes") or 0) <= 8192 for row in events),
    }


async def run_mcp_checks(
    client: Any,
    *,
    exercise_writes: bool,
    trace_reader: Callable[[list[str]], dict[str, Any]] = _trace_evidence,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> dict[str, Any]:
    tools = await client.list_tools()
    tool_names = {str(tool.name) for tool in tools}
    missing_tools = sorted(EXPECTED_TOOLS - tool_names)
    checks: list[dict[str, Any]] = [
        {
            "name": "tool_contract",
            "passed": not missing_tools,
            "detail": f"declared={len(tool_names)}, missing={missing_tools}",
        }
    ]
    correlation_ids: list[str] = []

    performance = _tool_payload(
        await client.call_tool_mcp(
            "get_stock_performance",
            {"ticker": "AAPL", "lookback_days": 30},
        )
    )
    correlation_ids.append(_correlation_id(performance))
    performance_ok = (
        performance.get("status") == "success"
        and performance.get("ticker") == "AAPL"
        and bool(performance.get("as_of"))
        and str(performance.get("source") or "").startswith("Unity Catalog")
    )
    checks.append(
        {
            "name": "governed_performance_retrieval",
            "passed": performance_ok,
            "detail": (
                f"status={performance.get('status')}, as_of={performance.get('as_of')}"
                f"{_safe_failure_detail(performance)}"
            ),
        }
    )

    semantic = _tool_payload(
        await client.call_tool_mcp(
            "semantic_research",
            {
                "query": "What production problems caused Apple stock to fall?",
                "top_k": 3,
                "tickers": ["AAPL"],
                "source_types": ["article"],
            },
        )
    )
    correlation_ids.append(_correlation_id(semantic))
    matches = semantic.get("matches") if isinstance(semantic.get("matches"), list) else []
    provenance_ok = bool(matches) and all(
        isinstance(match, dict)
        and all(match.get(field) not in (None, "") for field in ("source_type", "source_id", "ticker", "title"))
        for match in matches
    )
    checks.append(
        {
            "name": "semantic_retrieval",
            "passed": semantic.get("status") == "success" and provenance_ok,
            "detail": (
                f"status={semantic.get('status')}, matches={len(matches)}, "
                f"provenance_complete={provenance_ok}{_safe_failure_detail(semantic)}"
            ),
        }
    )

    write_summary: dict[str, Any] = {"exercised": False}
    if exercise_writes:
        before = _tool_payload(await client.call_tool_mcp("get_watchlist", {"watchlist_name": "Primary"}))
        correlation_ids.append(_correlation_id(before))
        ticker = _choose_disposable_ticker(before)
        idempotency_key = f"phase5-{uuid.uuid4().hex}"
        add_args = {
            "ticker": ticker,
            "action": "add",
            "watchlist_name": "Primary",
            "confirmed": True,
            "idempotency_key": idempotency_key,
        }
        first = _tool_payload(await client.call_tool_mcp("update_watchlist", add_args))
        try:
            replay = _tool_payload(await client.call_tool_mcp("update_watchlist", add_args))
            conflict = _tool_payload(
                await client.call_tool_mcp(
                    "update_watchlist",
                    {**add_args, "action": "remove"},
                )
            )
        finally:
            cleanup = _tool_payload(
                await client.call_tool_mcp(
                    "update_watchlist",
                    {
                        **add_args,
                        "action": "remove",
                        "idempotency_key": f"phase5-cleanup-{uuid.uuid4().hex}",
                    },
                )
            )
        after = _tool_payload(await client.call_tool_mcp("get_watchlist", {"watchlist_name": "Primary"}))
        for payload in (first, replay, conflict, cleanup, after):
            correlation_ids.append(_correlation_id(payload))
        after_tickers = {
            str(item.get("ticker") or "").upper()
            for item in after.get("tickers", [])
            if isinstance(item, dict)
        }
        idempotency_ok = (
            first.get("status") == "success"
            and first.get("idempotent_replay") is False
            and replay.get("status") == "success"
            and replay.get("idempotent_replay") is True
            and conflict.get("status") == "error"
            and "already used" in str(conflict.get("message") or "")
        )
        cleanup_ok = cleanup.get("status") == "success" and ticker not in after_tickers
        checks.extend(
            [
                {
                    "name": "write_idempotency",
                    "passed": idempotency_ok,
                    "detail": (
                        f"first_replay={first.get('idempotent_replay')}, "
                        f"retry_replay={replay.get('idempotent_replay')}, conflict_status={conflict.get('status')}"
                    ),
                },
                {
                    "name": "write_cleanup",
                    "passed": cleanup_ok,
                    "detail": f"ticker={ticker}, cleanup_status={cleanup.get('status')}, present_after={ticker in after_tickers}",
                },
            ]
        )
        write_summary = {
            "exercised": True,
            "ticker": ticker,
            "idempotent_replay_proved": idempotency_ok,
            "cleanup_proved": cleanup_ok,
        }

    expected_ids = sorted(correlation_ids)
    evidence: dict[str, Any] = {}
    for attempt in range(3):
        evidence = trace_reader(correlation_ids)
        if (
            evidence.get("trace_correlation_ids") == expected_ids
            and evidence.get("event_correlation_ids") == expected_ids
        ):
            break
        if attempt < 2:
            await sleep(1.0)
    traces_ok = (
        evidence.get("trace_correlation_ids") == expected_ids
        and evidence.get("event_correlation_ids") == expected_ids
        and evidence.get("trace_payloads_bounded") is True
        and evidence.get("idempotency_values_redacted") is True
        and evidence.get("event_payloads_bounded") is True
    )
    checks.append(
        {
            "name": "bounded_trace_evidence",
            "passed": traces_ok,
            "detail": (
                f"expected={len(expected_ids)}, traces={evidence.get('trace_count', 0)}, "
                f"events={evidence.get('event_count', 0)}"
            ),
        }
    )
    return {
        "status": "passed" if all(check["passed"] for check in checks) else "failed",
        "tool_count": len(tool_names),
        "performance_as_of": performance.get("as_of"),
        "semantic_match_count": len(matches),
        "writes": write_summary,
        "trace_evidence": {
            "trace_count": evidence.get("trace_count", 0),
            "event_count": evidence.get("event_count", 0),
            "trace_payloads_bounded": evidence.get("trace_payloads_bounded", False),
            "idempotency_values_redacted": evidence.get("idempotency_values_redacted", False),
            "event_payloads_bounded": evidence.get("event_payloads_bounded", False),
        },
        "checks": checks,
    }


def _profile_authorization(workspace: WorkspaceClient) -> str:
    override = os.getenv("DATABRICKS_APP_BEARER_TOKEN")
    if override:
        return f"Bearer {override}"
    headers = workspace.config.authenticate()
    authorization = headers.get("Authorization") or headers.get("authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise RuntimeError("The selected profile did not provide a bearer token")
    return authorization


async def run_deployed(
    *,
    profile: str,
    app_name: str,
    exercise_writes: bool,
    timeout_seconds: int,
) -> dict[str, Any]:
    if not profile.strip():
        raise ValueError("An explicit Databricks profile is required")
    os.environ["DATABRICKS_CONFIG_PROFILE"] = profile
    os.environ.setdefault("SIGNAL_DESK_SCHEMA", "bootcamp_students")
    os.environ.setdefault("SIGNAL_DESK_TABLE_SUFFIX", "srini")
    os.environ.setdefault("SIGNAL_DESK_GRAPH_SCHEMA", "bootcamp_cdc")
    workspace = WorkspaceClient(profile=profile)
    app = workspace.apps.get(app_name)
    app_url = str(getattr(app, "url", "") or "").rstrip("/")
    if not app_url.startswith("https://"):
        raise RuntimeError(f"Databricks app {app_name!r} does not expose a valid HTTPS URL")
    authorization = _profile_authorization(workspace)
    health = requests.get(
        f"{app_url}/health",
        headers={"Authorization": authorization},
        timeout=timeout_seconds,
    )
    health.raise_for_status()
    health_payload = health.json()
    health_ok = health_payload == {
        "status": "ok",
        "service": "stock-market-research",
        "contract_version": "1.0",
    }

    from fastmcp import Client

    async with Client(
        f"{app_url}/mcp",
        auth=authorization.removeprefix("Bearer "),
        timeout=timeout_seconds,
    ) as client:
        report = await run_mcp_checks(client, exercise_writes=exercise_writes)
    report["app_name"] = app_name
    report["app_url"] = app_url
    report["health"] = {"passed": health_ok, "status_code": health.status_code}
    if not health_ok:
        report["status"] = "failed"
    return report


async def run_render(
    *,
    service_url: str,
    bearer_token: str,
    exercise_writes: bool,
    timeout_seconds: int,
) -> dict[str, Any]:
    parsed = urlparse(service_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Render MCP URL must be HTTPS without embedded credentials")
    if len(bearer_token) < 32 or any(character.isspace() for character in bearer_token):
        raise ValueError("Render MCP machine credential is missing or invalid")
    base_url = service_url.rstrip("/")
    health = requests.get(f"{base_url}/health", timeout=timeout_seconds)
    health.raise_for_status()
    health_payload = health.json()
    health_ok = health_payload == {
        "status": "ok",
        "service": "stock-market-research",
        "contract_version": "1.0",
    }

    from fastmcp import Client
    from fastmcp.client.transports import StreamableHttpTransport

    request_id = f"phase5-{uuid.uuid4()}"
    transport = StreamableHttpTransport(
        f"{base_url}/mcp",
        headers={"X-Request-ID": request_id},
        auth=bearer_token,
    )
    async with Client(transport, timeout=timeout_seconds) as client:
        report = await run_mcp_checks(client, exercise_writes=exercise_writes)
    report["deployment"] = "render"
    report["service_url"] = base_url
    report["health"] = {"passed": health_ok, "status_code": health.status_code}
    if not health_ok:
        report["status"] = "failed"
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile")
    parser.add_argument("--app-name", default="signal-desk-mcp-dev")
    parser.add_argument("--url", help="Render MCP service base URL; switches the harness to Render mode.")
    parser.add_argument(
        "--bearer-env",
        default="MCP_SUPERVISOR_TOKEN",
        help="Environment variable containing the Render MCP machine credential.",
    )
    parser.add_argument(
        "--exercise-writes",
        action="store_true",
        help="Run a confirmed idempotent watchlist add and guaranteed cleanup.",
    )
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.url:
        report = asyncio.run(
            run_render(
                service_url=args.url,
                bearer_token=os.getenv(args.bearer_env, ""),
                exercise_writes=args.exercise_writes,
                timeout_seconds=args.timeout_seconds,
            )
        )
    else:
        if not args.profile:
            raise SystemExit("--profile is required unless --url is supplied")
        report = asyncio.run(
            run_deployed(
                profile=args.profile,
                app_name=args.app_name,
                exercise_writes=args.exercise_writes,
                timeout_seconds=args.timeout_seconds,
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
