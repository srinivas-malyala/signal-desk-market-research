#!/usr/bin/env python3
"""Prove the shared Lakebase Massive quota across a Databricks Job and Render MCP."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from databricks.sdk import WorkspaceClient

ROOT = Path(__file__).resolve().parents[1]
MCP_ROOT = ROOT / "mcp_server"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--job-id", required=True, type=int)
    parser.add_argument("--job-date", required=True, type=date.fromisoformat)
    parser.add_argument("--mcp-url", required=True)
    parser.add_argument("--token-env", default="MCP_SUPERVISOR_TOKEN")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    return parser


def _configure(profile: str) -> Any:
    os.environ["DATABRICKS_CONFIG_PROFILE"] = profile
    os.environ.setdefault("SIGNAL_DESK_SCHEMA", "bootcamp_students")
    os.environ.setdefault("SIGNAL_DESK_TABLE_SUFFIX", "srini")
    os.environ.setdefault("SIGNAL_DESK_GRAPH_SCHEMA", "bootcamp_cdc")
    if str(MCP_ROOT) not in os.sys.path:
        os.sys.path.insert(0, str(MCP_ROOT))
    import lakebase

    return lakebase


def _quota_state(lakebase: Any) -> dict[str, Any]:
    table = lakebase.table_name("massive_api_attempts")
    return lakebase.query(
        f"""SELECT clock_timestamp() AS observed_at, COUNT(*) AS active_count,
        COALESCE(EXTRACT(EPOCH FROM
          (MIN(acquired_at) + interval '60 seconds' - clock_timestamp())), 0) AS wait_seconds
        FROM {table}
        WHERE acquired_at > clock_timestamp() - interval '60 seconds'"""
    )[0]


def _wait_for_empty_window(lakebase: Any, timeout_seconds: int) -> datetime:
    deadline = time.monotonic() + timeout_seconds
    while True:
        state = _quota_state(lakebase)
        if int(state["active_count"]) == 0:
            return state["observed_at"]
        wait_for = max(float(state["wait_seconds"]), 0.0) + 1.0
        if time.monotonic() + wait_for > deadline:
            raise TimeoutError("Timed out waiting for the shared Massive quota window to clear")
        time.sleep(wait_for)


async def _one_mcp_call(url: str, token: str, timeout_seconds: int) -> dict[str, Any]:
    from fastmcp import Client
    from fastmcp.client.transports import StreamableHttpTransport

    transport = StreamableHttpTransport(
        f"{url.rstrip('/')}/mcp",
        headers={"X-Request-ID": f"p4-quota-{uuid.uuid4()}"},
        auth=token,
    )
    started = time.perf_counter()
    async with Client(transport, timeout=timeout_seconds) as client:
        result = await client.call_tool_mcp(
            "get_stock_performance",
            {"ticker": "AAPL", "lookback_days": 30},
        )
    elapsed = time.perf_counter() - started
    structured = getattr(result, "structured_content", None) or getattr(
        result, "structuredContent", None
    )
    if not isinstance(structured, dict):
        for block in getattr(result, "content", []) or []:
            if isinstance(getattr(block, "text", None), str):
                candidate = json.loads(block.text)
                if isinstance(candidate, dict):
                    structured = candidate
                    break
    if not isinstance(structured, dict):
        raise RuntimeError("MCP quota probe returned no structured result")
    return {
        "status": structured.get("status"),
        "correlation_id": structured.get("correlation_id"),
        "elapsed_seconds": round(elapsed, 3),
    }


async def _mcp_calls(url: str, token: str, timeout_seconds: int) -> list[dict[str, Any]]:
    return await asyncio.gather(
        *(_one_mcp_call(url, token, timeout_seconds) for _ in range(4))
    )


def _job_output(workspace: WorkspaceClient, completed: Any) -> dict[str, Any]:
    refreshed = workspace.jobs.get_run(int(completed.run_id))
    tasks = list(getattr(refreshed, "tasks", None) or [])
    successful = [
        task
        for task in tasks
        if getattr(getattr(task, "state", None), "result_state", None)
        and getattr(task.state.result_state, "value", "") == "SUCCESS"
        and getattr(task, "run_id", None)
    ]
    if not successful:
        raise RuntimeError("Completed job had no successful task attempt")
    output = workspace.jobs.get_run_output(successful[-1].run_id)
    logs = str(getattr(output, "logs", "") or "")
    for line in reversed(logs.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            candidate = json.loads(line)
            if isinstance(candidate, dict) and "http_attempts" in candidate:
                return candidate
    raise RuntimeError("Job output did not contain the bounded ingestion metrics")


def _ledger(lakebase: Any, started_at: datetime) -> list[dict[str, Any]]:
    table = lakebase.table_name("massive_api_attempts")
    return lakebase.query(
        f"""SELECT acquired_at, requester, contract_version
        FROM {table}
        WHERE acquired_at >= %s
        ORDER BY acquired_at, attempt_id""",
        (started_at,),
    )


def _rolling_max(rows: list[dict[str, Any]]) -> int:
    values = [row["acquired_at"] for row in rows]
    return max(
        (
            sum(1 for candidate in values if current - timedelta(seconds=60) < candidate <= current)
            for current in values
        ),
        default=0,
    )


def main() -> int:
    args = _parser().parse_args()
    parsed = urlparse(args.mcp_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("MCP URL must be HTTPS without embedded credentials")
    token = os.getenv(args.token_env, "")
    if len(token) < 32 or any(character.isspace() for character in token):
        raise ValueError(f"{args.token_env} is missing or invalid")

    lakebase = _configure(args.profile)
    started_at = _wait_for_empty_window(lakebase, args.timeout_seconds)
    workspace = WorkspaceClient(profile=args.profile)
    idempotency_token = f"p4-quota-{uuid.uuid4().hex}"
    waiter = workspace.jobs.run_now(
        args.job_id,
        idempotency_token=idempotency_token,
        job_parameters={
            "catalog": "bootcamp_students",
            "schema": "student_sri",
            "volume": "signal_desk_raw",
            "start_date": args.job_date.isoformat(),
            "end_date": args.job_date.isoformat(),
            "max_dates": "1",
            "stop_after_row_estimate": "0",
        },
    )
    run_id = int(waiter.response.run_id)
    mcp_results = asyncio.run(_mcp_calls(args.mcp_url, token, args.timeout_seconds))
    completed = waiter.result(timeout=timedelta(seconds=args.timeout_seconds))
    job_metrics = _job_output(workspace, completed)
    rows = _ledger(lakebase, started_at)

    fifth_gap = None
    if len(rows) >= 5:
        fifth_gap = (rows[4]["acquired_at"] - rows[0]["acquired_at"]).total_seconds()
    requester_counts: dict[str, int] = {}
    for row in rows:
        requester = str(row["requester"])
        requester_counts[requester] = requester_counts.get(requester, 0) + 1
    expected_attempts = 4 + int(job_metrics.get("http_attempts") or 0)
    rolling_max = _rolling_max(rows)
    checks = {
        "job_succeeded": str(getattr(completed.state.result_state, "value", "")) == "SUCCESS",
        "four_mcp_calls_completed": len(mcp_results) == 4
        and all(result["status"] == "success" for result in mcp_results),
        "job_made_one_physical_attempt": int(job_metrics.get("http_attempts") or 0) == 1,
        "both_hosts_recorded": requester_counts.get("render-mcp") == 4
        and requester_counts.get("databricks-market-ingestion") == 1,
        "no_request_bypassed_lakebase": len(rows) == expected_attempts == 5,
        "rolling_maximum_is_four": rolling_max == 4,
        "fifth_acquisition_waited": fifth_gap is not None and fifth_gap >= 59.0,
    }
    report = {
        "status": "passed" if all(checks.values()) else "failed",
        "checked_at": datetime.now(UTC).isoformat(),
        "job": {
            "job_id": args.job_id,
            "run_id": run_id,
            "date": args.job_date.isoformat(),
            "http_attempts": job_metrics.get("http_attempts"),
            "api_dates": job_metrics.get("api_dates"),
            "result_state": getattr(completed.state.result_state, "value", None),
        },
        "mcp": {
            "request_count": len(mcp_results),
            "statuses": [result["status"] for result in mcp_results],
            "elapsed_seconds": [result["elapsed_seconds"] for result in mcp_results],
        },
        "ledger": {
            "row_count": len(rows),
            "requester_counts": requester_counts,
            "rolling_60_second_maximum": rolling_max,
            "fifth_acquisition_gap_seconds": round(fifth_gap, 3) if fifth_gap is not None else None,
            "contract_versions": sorted({int(row["contract_version"]) for row in rows}),
        },
        "checks": checks,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
