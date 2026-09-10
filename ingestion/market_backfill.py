"""Checkpointed, immutable Massive grouped-market landing job."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingestion.checkpoints import CheckpointStore, eligible_weekdays  # noqa: E402
from mcp_server.massive_client import (  # noqa: E402
    MassiveClient,
    MassiveResponse,
    MassiveResponseError,
    ProcessSafeRollingLimiter,
)


class LandingIntegrityError(RuntimeError):
    """Raised when existing landing data is incomplete or inconsistent."""


@dataclass(frozen=True)
class BackfillConfig:
    raw_root: Path
    start_date: date
    end_date: date
    max_dates: int = 10
    stop_after_rows: int | None = None
    retry_terminal: bool = False
    today: date | None = None

    def __post_init__(self) -> None:
        if not 1 <= self.max_dates <= 504:
            raise ValueError("max_dates must be between 1 and 504")
        if self.stop_after_rows is not None and self.stop_after_rows < 1:
            raise ValueError("stop_after_rows must be positive")


@dataclass
class BackfillMetrics:
    planned_dates: int = 0
    claimed_dates: int = 0
    api_dates: int = 0
    replayed_dates: int = 0
    skipped_dates: int = 0
    completed_dates: int = 0
    no_data_dates: int = 0
    retryable_failures: int = 0
    terminal_failures: int = 0
    landed_rows: int = 0
    landed_bytes: int = 0
    available_rows: int = 0


def _canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")


def atomic_write(path: Path, content: bytes) -> None:
    """Replace a file only after its complete contents are flushed to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as temporary:
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


class DailyLandingStore:
    """Write and validate immutable response/manifest pairs by trading date."""

    def __init__(
        self,
        root: Path,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.root = root
        self.clock = clock

    def date_directory(self, trading_date: date) -> Path:
        return self.root / "market_daily" / f"trading_date={trading_date.isoformat()}"

    def response_path(self, trading_date: date) -> Path:
        return self.date_directory(trading_date) / "response.json"

    def manifest_path(self, trading_date: date) -> Path:
        return self.date_directory(trading_date) / "manifest.json"

    def read_manifest(self, trading_date: date) -> dict[str, Any] | None:
        response_path = self.response_path(trading_date)
        manifest_path = self.manifest_path(trading_date)
        if not response_path.exists() and not manifest_path.exists():
            return None
        if not response_path.exists() or not manifest_path.exists():
            raise LandingIntegrityError(f"Incomplete landing pair for {trading_date}")
        try:
            response_bytes = response_path.read_bytes()
            payload = json.loads(response_bytes)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise LandingIntegrityError(f"Unreadable landing pair for {trading_date}") from error
        results = payload.get("results", []) if isinstance(payload, dict) else None
        checksum = hashlib.sha256(response_bytes).hexdigest()
        if (
            not isinstance(manifest, dict)
            or manifest.get("version") != 1
            or manifest.get("trading_date") != trading_date.isoformat()
            or not isinstance(results, list)
            or manifest.get("row_count") != len(results)
            or manifest.get("checksum_sha256") != checksum
        ):
            raise LandingIntegrityError(f"Landing checksum or manifest mismatch for {trading_date}")
        return manifest

    def land(self, trading_date: date, response: MassiveResponse) -> dict[str, Any]:
        existing = self.read_manifest(trading_date)
        if existing is not None:
            return existing
        results = response.payload.get("results", [])
        if not isinstance(results, list):
            raise MassiveResponseError("Massive grouped daily results must be a list")
        response_bytes = _canonical_json_bytes(response.payload)
        response_path = self.response_path(trading_date)
        manifest_path = self.manifest_path(trading_date)
        atomic_write(response_path, response_bytes)
        manifest = {
            "version": 1,
            "source": "massive",
            "dataset": "grouped_daily",
            "trading_date": trading_date.isoformat(),
            "endpoint": f"/v2/aggs/grouped/locale/us/market/stocks/{trading_date.isoformat()}",
            "adjusted": True,
            "include_otc": True,
            "request_id": response.observation.massive_request_id,
            "correlation_id": response.observation.correlation_id,
            "status_code": response.observation.status_code,
            "row_count": len(results),
            "byte_count": len(response_bytes),
            "checksum_sha256": hashlib.sha256(response_bytes).hexdigest(),
            "elapsed_ms": response.observation.elapsed_ms,
            "landed_at": self.clock().isoformat(),
            "response_path": str(response_path),
        }
        atomic_write(manifest_path, _canonical_json_bytes(manifest))
        return manifest


def _is_retryable(error: BaseException) -> bool:
    if isinstance(error, (requests.Timeout, requests.ConnectionError, OSError)):
        return True
    if isinstance(error, requests.HTTPError) and error.response is not None:
        return error.response.status_code == 429 or error.response.status_code >= 500
    return False


def run_backfill(
    config: BackfillConfig,
    client: MassiveClient,
    *,
    checkpoint_store: CheckpointStore | None = None,
    landing_store: DailyLandingStore | None = None,
) -> BackfillMetrics:
    checkpoints = checkpoint_store or CheckpointStore(config.raw_root / "_control" / "market_checkpoints.json")
    landings = landing_store or DailyLandingStore(config.raw_root)
    candidates = eligible_weekdays(
        config.start_date,
        config.end_date,
        today=config.today,
    )[: config.max_dates]
    checkpoints.ensure_pending(candidates)
    metrics = BackfillMetrics(planned_dates=len(candidates))

    for trading_date in candidates:
        claim = checkpoints.claim(trading_date, retry_terminal=config.retry_terminal)
        if claim is None:
            metrics.skipped_dates += 1
            existing = landings.read_manifest(trading_date)
            if existing is not None:
                metrics.available_rows += existing["row_count"]
                if config.stop_after_rows and metrics.available_rows >= config.stop_after_rows:
                    break
            continue
        metrics.claimed_dates += 1
        try:
            manifest = landings.read_manifest(trading_date)
            if manifest is None:
                response = client.get_daily_market_summary(trading_date, include_otc=True)
                metrics.api_dates += 1
                manifest = landings.land(trading_date, response)
            else:
                metrics.replayed_dates += 1
            checkpoints.complete(
                trading_date,
                request_id=manifest.get("request_id"),
                landing_path=manifest["response_path"],
                row_count=manifest["row_count"],
                checksum=manifest["checksum_sha256"],
            )
            metrics.landed_rows += manifest["row_count"]
            metrics.landed_bytes += manifest["byte_count"]
            metrics.available_rows += manifest["row_count"]
            if manifest["row_count"] == 0:
                metrics.no_data_dates += 1
            else:
                metrics.completed_dates += 1
            if config.stop_after_rows and metrics.available_rows >= config.stop_after_rows:
                break
        except Exception as error:
            retryable = _is_retryable(error)
            checkpoints.fail(trading_date, error, retryable=retryable)
            if retryable:
                metrics.retryable_failures += 1
            else:
                metrics.terminal_failures += 1
    return metrics


def _default_dates(max_dates: int) -> tuple[date, date]:
    end_date = date.today() - timedelta(days=1)
    cursor = end_date
    weekdays = 0
    while weekdays < max_dates:
        if cursor.weekday() < 5:
            weekdays += 1
        if weekdays < max_dates:
            cursor -= timedelta(days=1)
    return cursor, end_date


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--volume", required=True)
    parser.add_argument("--raw-root", type=Path, help="Local/test override for the Volume root")
    parser.add_argument("--profile", help="Explicit Databricks profile for local secret lookup")
    parser.add_argument("--start-date", type=lambda value: date.fromisoformat(value) if value else None)
    parser.add_argument("--end-date", type=lambda value: date.fromisoformat(value) if value else None)
    parser.add_argument("--max-dates", type=int, default=10)
    parser.add_argument("--stop-after-row-estimate", type=int)
    parser.add_argument("--retry-terminal", action="store_true")
    args = parser.parse_args(argv)
    if (args.start_date is None) != (args.end_date is None):
        parser.error("--start-date and --end-date must be supplied together")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    start_date, end_date = (
        (args.start_date, args.end_date) if args.start_date is not None else _default_dates(args.max_dates)
    )
    raw_root = args.raw_root or Path(f"/Volumes/{args.catalog}/{args.schema}/{args.volume}")
    limiter = ProcessSafeRollingLimiter(raw_root / "_control" / "massive_rate_limit.json")
    client = MassiveClient(limiter=limiter, databricks_profile=args.profile)
    metrics = run_backfill(
        BackfillConfig(
            raw_root=raw_root,
            start_date=start_date,
            end_date=end_date,
            max_dates=args.max_dates,
            stop_after_rows=(
                args.stop_after_row_estimate
                if args.stop_after_row_estimate and args.stop_after_row_estimate > 0
                else None
            ),
            retry_terminal=args.retry_terminal,
        ),
        client,
    )
    output = {**asdict(metrics), **client.metrics()}
    print(json.dumps(output, sort_keys=True))
    return 1 if metrics.retryable_failures or metrics.terminal_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
