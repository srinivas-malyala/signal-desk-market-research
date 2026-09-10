from __future__ import annotations

from shared.market_certification import (
    MarketCertificationMetrics,
    build_market_certification,
    max_events_in_rolling_window,
)


def passing_metrics() -> MarketCertificationMetrics:
    return MarketCertificationMetrics(
        api_attempts=68,
        max_attempts_in_rolling_minute=4,
        manifest_dates=68,
        manifest_rows=1_100_000,
        manifest_bytes=125_000_000,
        successful_api_elapsed_ms=42_000,
        bronze_rows=1_100_000,
        silver_rows=1_050_000,
        quarantine_rows=50_000,
        silver_distinct_keys=1_050_000,
        duplicate_silver_keys=0,
        minimum_trading_date="2026-06-01",
        maximum_trading_date="2026-09-09",
    )


def test_rolling_window_treats_exact_boundary_as_new_window() -> None:
    assert max_events_in_rolling_window([0, 0, 0, 0, 60, 60, 60, 60]) == 4
    assert max_events_in_rolling_window([0, 1, 2, 3, 59.999]) == 5
    assert max_events_in_rolling_window([]) == 0


def test_certification_passes_only_measured_reconciled_distinct_rows() -> None:
    report = build_market_certification(passing_metrics())
    assert report["status"] == "PASSED"
    assert all(report["checks"].values())


def test_certification_requires_strictly_more_than_one_million() -> None:
    values = passing_metrics().__dict__ | {"silver_rows": 1_000_000, "silver_distinct_keys": 1_000_000}
    report = build_market_certification(MarketCertificationMetrics(**values))
    assert report["status"] == "FAILED"
    assert report["checks"]["more_than_one_million_distinct_rows"] is False


def test_certification_detects_rate_and_reconciliation_failures() -> None:
    values = passing_metrics().__dict__ | {
        "max_attempts_in_rolling_minute": 5,
        "quarantine_rows": 49_999,
    }
    report = build_market_certification(MarketCertificationMetrics(**values))
    assert report["status"] == "FAILED"
    assert report["checks"]["massive_free_rate_limit_respected"] is False
    assert report["checks"]["silver_and_quarantine_reconcile_to_bronze"] is False
