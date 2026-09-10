from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from ingestion.checkpoints import CheckpointStatus, CheckpointStore
from ingestion.market_backfill import (
    BackfillConfig,
    DailyLandingStore,
    LandingIntegrityError,
    atomic_write,
    run_backfill,
)
from mcp_server.massive_client import MassiveResponse, RequestObservation


def envelope(trading_date: date, rows: int = 2) -> MassiveResponse:
    return MassiveResponse(
        payload={
            "status": "OK",
            "request_id": f"request-{trading_date}",
            "results": [{"T": f"TICKER{index}", "v": index} for index in range(rows)],
        },
        observation=RequestObservation(
            correlation_id=f"correlation-{trading_date}",
            massive_request_id=f"request-{trading_date}",
            status_code=200,
            elapsed_ms=25,
            bytes_received=100,
            result_count=rows,
            attempt=1,
        ),
    )


def config(tmp_path: Path, start: date, end: date, max_dates: int = 10) -> BackfillConfig:
    return BackfillConfig(
        raw_root=tmp_path / "raw",
        start_date=start,
        end_date=end,
        max_dates=max_dates,
        today=date(2026, 9, 10),
    )


def test_two_date_run_lands_atomic_response_and_manifest_pairs(tmp_path: Path) -> None:
    client = Mock()
    client.get_daily_market_summary.side_effect = lambda trading_date, **_kwargs: envelope(trading_date)
    settings = config(tmp_path, date(2026, 9, 8), date(2026, 9, 9))
    metrics = run_backfill(settings, client)

    assert metrics.api_dates == 2
    assert metrics.completed_dates == 2
    assert metrics.landed_rows == 4
    for trading_date in (date(2026, 9, 8), date(2026, 9, 9)):
        directory = settings.raw_root / "market_daily" / f"trading_date={trading_date}"
        payload = json.loads((directory / "response.json").read_text())
        manifest = json.loads((directory / "manifest.json").read_text())
        assert len(payload["results"]) == manifest["row_count"] == 2
        assert manifest["include_otc"] is True
        assert manifest["adjusted"] is True
        assert not list(directory.glob("*.tmp"))


def test_rerun_skips_completed_dates_without_api_calls(tmp_path: Path) -> None:
    settings = config(tmp_path, date(2026, 9, 8), date(2026, 9, 9))
    first_client = Mock()
    first_client.get_daily_market_summary.side_effect = lambda trading_date, **_kwargs: envelope(trading_date)
    run_backfill(settings, first_client)

    second_client = Mock()
    metrics = run_backfill(settings, second_client)
    assert metrics.skipped_dates == 2
    second_client.get_daily_market_summary.assert_not_called()


def test_existing_valid_landing_replays_without_api_call(tmp_path: Path) -> None:
    trading_date = date(2026, 9, 9)
    settings = config(tmp_path, trading_date, trading_date)
    landing_store = DailyLandingStore(settings.raw_root)
    landing_store.land(trading_date, envelope(trading_date))
    client = Mock()

    metrics = run_backfill(settings, client)
    assert metrics.replayed_dates == 1
    assert metrics.api_dates == 0
    client.get_daily_market_summary.assert_not_called()


def test_empty_holiday_response_is_completed_as_no_data(tmp_path: Path) -> None:
    trading_date = date(2026, 9, 7)
    settings = config(tmp_path, trading_date, trading_date)
    client = Mock()
    client.get_daily_market_summary.return_value = envelope(trading_date, rows=0)
    metrics = run_backfill(settings, client)
    checkpoint = CheckpointStore(settings.raw_root / "_control" / "market_checkpoints.json").snapshot()
    assert metrics.no_data_dates == 1
    assert checkpoint[trading_date.isoformat()].status is CheckpointStatus.NO_DATA


def test_retryable_failure_resumes_on_next_run(tmp_path: Path) -> None:
    trading_date = date(2026, 9, 9)
    settings = config(tmp_path, trading_date, trading_date)
    failing = Mock()
    failing.get_daily_market_summary.side_effect = requests.Timeout("timeout")
    first_metrics = run_backfill(settings, failing)
    assert first_metrics.retryable_failures == 1

    succeeding = Mock()
    succeeding.get_daily_market_summary.return_value = envelope(trading_date)
    second_metrics = run_backfill(settings, succeeding)
    assert second_metrics.completed_dates == 1
    checkpoint = CheckpointStore(settings.raw_root / "_control" / "market_checkpoints.json").snapshot()
    assert checkpoint[trading_date.isoformat()].attempt_count == 2


def test_manifest_checksum_mismatch_fails_closed(tmp_path: Path) -> None:
    trading_date = date(2026, 9, 9)
    store = DailyLandingStore(tmp_path)
    store.land(trading_date, envelope(trading_date))
    store.response_path(trading_date).write_text('{"results": []}\n')
    with pytest.raises(LandingIntegrityError):
        store.read_manifest(trading_date)


def test_incomplete_landing_pair_is_never_treated_as_complete(tmp_path: Path) -> None:
    trading_date = date(2026, 9, 9)
    store = DailyLandingStore(tmp_path)
    atomic_write(store.response_path(trading_date), b'{"results": []}\n')
    with pytest.raises(LandingIntegrityError, match="Incomplete landing pair"):
        store.read_manifest(trading_date)


def test_atomic_write_does_not_publish_partial_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "response.json"

    def fail_replace(_source, _target) -> None:
        raise OSError("simulated interruption")

    monkeypatch.setattr("ingestion.market_backfill.os.replace", fail_replace)
    with pytest.raises(OSError):
        atomic_write(target, b"complete-content")
    assert not target.exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_stop_after_row_target_bounds_api_calls(tmp_path: Path) -> None:
    client = Mock()
    client.get_daily_market_summary.side_effect = lambda trading_date, **_kwargs: envelope(trading_date, rows=3)
    settings = BackfillConfig(
        raw_root=tmp_path / "raw",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 9),
        max_dates=10,
        stop_after_rows=5,
        today=date(2026, 9, 10),
    )
    metrics = run_backfill(settings, client)
    assert metrics.api_dates == 2
    assert metrics.landed_rows == 6


def test_manifest_records_injected_utc_clock(tmp_path: Path) -> None:
    fixed = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
    store = DailyLandingStore(tmp_path, clock=lambda: fixed)
    manifest = store.land(date(2026, 9, 9), envelope(date(2026, 9, 9)))
    assert manifest["landed_at"] == fixed.isoformat()
