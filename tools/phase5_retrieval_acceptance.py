#!/usr/bin/env python3
"""Run sanitized workspace acceptance for the governed market retrieval path."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from databricks.sdk import WorkspaceClient

ROOT = Path(__file__).resolve().parents[1]
MCP_ROOT = ROOT / "mcp_server"
GOVERNED_SOURCE = "Unity Catalog silver_market_bars joined to gold_stock_performance"


def _check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def evaluate_retrieval(
    performance: dict[str, Any],
    warehouse_rows: list[dict[str, Any]],
    *,
    today: date,
    max_staleness_days: int,
    massive_attempts: int,
) -> dict[str, Any]:
    """Evaluate only bounded, non-secret evidence from one live retrieval."""
    checks: list[dict[str, Any]] = []
    success = performance.get("status") == "success"
    checks.append(_check("tool_status", success, f"status={performance.get('status')}"))

    source = str(performance.get("source") or "")
    checks.append(
        _check(
            "governed_history_preferred",
            source == GOVERNED_SOURCE,
            f"source={source or 'missing'}",
        )
    )

    returned_rows = performance.get("daily_bars") if isinstance(performance.get("daily_bars"), list) else []
    checks.append(
        _check(
            "bounded_result",
            0 < len(returned_rows) <= 370,
            f"returned_rows={len(returned_rows)}, bound=370",
        )
    )
    checks.append(
        _check(
            "independent_reconciliation",
            bool(warehouse_rows) and returned_rows == warehouse_rows,
            f"tool_rows={len(returned_rows)}, independently_read_rows={len(warehouse_rows)}",
        )
    )

    as_of_text = str(performance.get("as_of") or "")
    try:
        as_of = date.fromisoformat(as_of_text)
        staleness_days = (today - as_of).days
    except ValueError:
        as_of = None
        staleness_days = None
    freshness_ok = (
        as_of is not None
        and staleness_days is not None
        and 0 <= staleness_days <= max_staleness_days
    )
    checks.append(
        _check(
            "freshness",
            freshness_ok,
            f"as_of={as_of_text or 'missing'}, staleness_days={staleness_days}, maximum={max_staleness_days}",
        )
    )

    expected_change = None
    if warehouse_rows:
        first_close = warehouse_rows[0].get("close")
        last_close = warehouse_rows[-1].get("close")
        if first_close not in (None, 0) and last_close is not None:
            expected_change = round((last_close - first_close) / first_close * 100, 2)
    actual_change = performance.get("change_percent")
    checks.append(
        _check(
            "known_answer_return",
            expected_change is not None and actual_change == expected_change,
            f"expected_change_percent={expected_change}, actual_change_percent={actual_change}",
        )
    )

    snapshot = performance.get("current_snapshot")
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    snapshot_available = snapshot.get("available") is True
    safe_entitlement = (
        snapshot.get("available") is False
        and isinstance(snapshot.get("message"), str)
        and bool(snapshot.get("message"))
        and snapshot.get("fallback") == "latest daily aggregate"
    )
    checks.append(
        _check(
            "snapshot_or_safe_entitlement_fallback",
            snapshot_available or safe_entitlement,
            f"snapshot_available={snapshot_available}, safe_fallback={safe_entitlement}",
        )
    )
    checks.append(
        _check(
            "massive_free_plan_budget",
            0 <= massive_attempts <= 4,
            f"physical_attempts={massive_attempts}, rolling_minute_budget=4",
        )
    )

    return {
        "status": "passed" if all(item["passed"] for item in checks) else "failed",
        "ticker": performance.get("ticker"),
        "as_of": as_of_text or None,
        "warehouse_row_count": len(warehouse_rows),
        "change_percent": actual_change,
        "snapshot_available": snapshot_available,
        "massive_http_attempts": massive_attempts,
        "checks": checks,
    }


def run_acceptance(
    *,
    profile: str,
    warehouse_id: str,
    ticker: str,
    lookback_days: int,
    max_staleness_days: int,
    today: date | None = None,
    workspace: WorkspaceClient | None = None,
    performance_call: Callable[[str, int], dict[str, Any]] | None = None,
    market_fetch: Callable[..., list[dict[str, Any]]] | None = None,
    metrics_call: Callable[[], dict[str, int]] | None = None,
) -> dict[str, Any]:
    if not profile.strip():
        raise ValueError("An explicit Databricks profile is required")
    if not 2 <= lookback_days <= 365:
        raise ValueError("lookback_days must be between 2 and 365")
    if not 0 <= max_staleness_days <= 30:
        raise ValueError("max_staleness_days must be between 0 and 30")

    current_date = today or date.today()
    requested_start = current_date - timedelta(days=lookback_days)
    os.environ["DATABRICKS_CONFIG_PROFILE"] = profile
    os.environ["DATABRICKS_WAREHOUSE_ID"] = warehouse_id
    os.environ.setdefault("DATABRICKS_CATALOG", "bootcamp_students")
    os.environ.setdefault("DATABRICKS_SCHEMA", "student_sri")

    if str(MCP_ROOT) not in sys.path:
        sys.path.insert(0, str(MCP_ROOT))
    import lakehouse_market
    import research_broker

    active_workspace = workspace or WorkspaceClient(profile=profile)
    fetch = market_fetch or lakehouse_market.fetch_market_bars
    warehouse_rows = fetch(
        ticker,
        requested_start.isoformat(),
        current_date.isoformat(),
        workspace=active_workspace,
    )
    performance = (performance_call or research_broker.get_stock_performance)(ticker, lookback_days)
    metrics = (metrics_call or (lambda: research_broker.client().metrics()))()
    return evaluate_retrieval(
        performance,
        warehouse_rows,
        today=current_date,
        max_staleness_days=max_staleness_days,
        massive_attempts=int(metrics.get("http_attempts", 0)),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--warehouse-id", default="b15d3d6f837ba428")
    parser.add_argument("--ticker", default="AAPL")
    parser.add_argument("--lookback-days", type=int, default=30)
    parser.add_argument("--max-staleness-days", type=int, default=7)
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    report = run_acceptance(
        profile=args.profile,
        warehouse_id=args.warehouse_id,
        ticker=args.ticker.strip().upper(),
        lookback_days=args.lookback_days,
        max_staleness_days=args.max_staleness_days,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
    print(rendered)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
