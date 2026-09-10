"""Deterministic acceptance rules for the market-volume certification report."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

MINIMUM_DISTINCT_MARKET_ROWS = 1_000_000
MASSIVE_FREE_CALL_LIMIT = 4
MASSIVE_RATE_WINDOW_SECONDS = 60.0


@dataclass(frozen=True)
class MarketCertificationMetrics:
    api_attempts: int
    max_attempts_in_rolling_minute: int
    manifest_dates: int
    manifest_rows: int
    manifest_bytes: int
    successful_api_elapsed_ms: int
    bronze_rows: int
    silver_rows: int
    quarantine_rows: int
    silver_distinct_keys: int
    duplicate_silver_keys: int
    minimum_trading_date: str | None
    maximum_trading_date: str | None


def max_events_in_rolling_window(timestamps: list[float], window_seconds: float = 60.0) -> int:
    """Return the largest half-open [start, start + window) event count."""
    ordered = sorted(timestamps)
    left = 0
    maximum = 0
    for right, timestamp in enumerate(ordered):
        while timestamp - ordered[left] >= window_seconds:
            left += 1
        maximum = max(maximum, right - left + 1)
    return maximum


def build_market_certification(metrics: MarketCertificationMetrics) -> dict[str, Any]:
    """Evaluate all measurable capstone volume, quality, and quota gates."""
    checks = {
        "more_than_one_million_distinct_rows": metrics.silver_distinct_keys > MINIMUM_DISTINCT_MARKET_ROWS,
        "manifest_reconciles_to_bronze": metrics.manifest_rows == metrics.bronze_rows,
        "silver_and_quarantine_reconcile_to_bronze": (
            metrics.silver_rows + metrics.quarantine_rows == metrics.bronze_rows
        ),
        "silver_keys_are_unique": metrics.duplicate_silver_keys == 0
        and metrics.silver_distinct_keys == metrics.silver_rows,
        "massive_free_rate_limit_respected": (
            metrics.max_attempts_in_rolling_minute <= MASSIVE_FREE_CALL_LIMIT
        ),
        "date_range_present": bool(metrics.minimum_trading_date and metrics.maximum_trading_date),
    }
    return {
        "certification_version": 1,
        "certified_at": datetime.now(UTC).isoformat(),
        "status": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "metrics": asdict(metrics),
    }
