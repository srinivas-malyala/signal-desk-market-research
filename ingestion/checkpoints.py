"""Durable, atomic checkpoint state for the market-wide Massive backfill."""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any


class CheckpointError(RuntimeError):
    """Base exception for checkpoint validation and transitions."""


class CorruptCheckpointError(CheckpointError):
    """Raised when persisted state cannot be trusted."""


class CheckpointStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    NO_DATA = "no_data"
    RETRYABLE_FAILURE = "retryable_failure"
    TERMINAL_FAILURE = "terminal_failure"


TERMINAL_STATUSES = frozenset({CheckpointStatus.COMPLETED, CheckpointStatus.NO_DATA})


@dataclass(frozen=True)
class DateCheckpoint:
    trading_date: str
    status: CheckpointStatus
    attempt_count: int
    updated_at: str
    request_id: str | None = None
    landing_path: str | None = None
    row_count: int | None = None
    checksum: str | None = None
    error_type: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> DateCheckpoint:
        try:
            checkpoint = cls(
                trading_date=date.fromisoformat(value["trading_date"]).isoformat(),
                status=CheckpointStatus(value["status"]),
                attempt_count=int(value["attempt_count"]),
                updated_at=datetime.fromisoformat(value["updated_at"]).isoformat(),
                request_id=value.get("request_id"),
                landing_path=value.get("landing_path"),
                row_count=value.get("row_count"),
                checksum=value.get("checksum"),
                error_type=value.get("error_type"),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise CorruptCheckpointError("Checkpoint entry has an invalid shape") from error
        if checkpoint.attempt_count < 0 or (checkpoint.row_count is not None and checkpoint.row_count < 0):
            raise CorruptCheckpointError("Checkpoint counts cannot be negative")
        return checkpoint

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["status"] = self.status.value
        return value


def eligible_weekdays(
    start_date: date,
    end_date: date,
    *,
    today: date | None = None,
    history_days: int = 731,
) -> list[date]:
    """Return inclusive weekdays bounded to completed dates and free-plan history."""
    current = today or date.today()
    if start_date > end_date:
        raise ValueError("start_date must not be after end_date")
    if end_date >= current:
        raise ValueError("end_date must be earlier than today")
    if start_date < current - timedelta(days=history_days):
        raise ValueError(f"start_date exceeds the configured {history_days}-day history window")
    values: list[date] = []
    cursor = start_date
    while cursor <= end_date:
        if cursor.weekday() < 5:
            values.append(cursor)
        cursor += timedelta(days=1)
    return values


class CheckpointStore:
    """Persist date checkpoints using a lock and atomic same-directory replace."""

    VERSION = 1

    def __init__(
        self,
        path: Path,
        *,
        stale_after: timedelta = timedelta(hours=2),
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if stale_after <= timedelta(0):
            raise ValueError("stale_after must be positive")
        self.path = path
        self.lock_path = path.with_suffix(path.suffix + ".lock")
        self.stale_after = stale_after
        self.clock = clock

    def _read_unlocked(self) -> dict[str, DateCheckpoint]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if payload.get("version") != self.VERSION or not isinstance(payload.get("dates"), dict):
                raise ValueError
            checkpoints = {
                key: DateCheckpoint.from_dict(value) for key, value in payload["dates"].items()
            }
        except (OSError, json.JSONDecodeError, AttributeError, ValueError) as error:
            raise CorruptCheckpointError(f"Checkpoint file {self.path} is invalid") from error
        if any(key != value.trading_date for key, value in checkpoints.items()):
            raise CorruptCheckpointError("Checkpoint date keys do not match their entries")
        return checkpoints

    def _write_unlocked(self, checkpoints: dict[str, DateCheckpoint]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": self.VERSION,
            "updated_at": self.clock().isoformat(),
            "dates": {key: checkpoints[key].to_dict() for key in sorted(checkpoints)},
        }
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as temporary:
                json.dump(payload, temporary, indent=2, sort_keys=True)
                temporary.write("\n")
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, self.path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    def _locked_update(
        self, operation: Callable[[dict[str, DateCheckpoint]], Any]
    ) -> Any:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            checkpoints = self._read_unlocked()
            result = operation(checkpoints)
            self._write_unlocked(checkpoints)
            return result

    def ensure_pending(self, trading_dates: Iterable[date]) -> None:
        def update(checkpoints: dict[str, DateCheckpoint]) -> None:
            timestamp = self.clock().isoformat()
            for trading_date in trading_dates:
                key = trading_date.isoformat()
                checkpoints.setdefault(
                    key,
                    DateCheckpoint(
                        trading_date=key,
                        status=CheckpointStatus.PENDING,
                        attempt_count=0,
                        updated_at=timestamp,
                    ),
                )

        self._locked_update(update)

    def claim(self, trading_date: date, *, retry_terminal: bool = False) -> DateCheckpoint | None:
        key = trading_date.isoformat()

        def update(checkpoints: dict[str, DateCheckpoint]) -> DateCheckpoint | None:
            current = checkpoints.get(key)
            if current and current.status in TERMINAL_STATUSES:
                return None
            if current and current.status is CheckpointStatus.TERMINAL_FAILURE and not retry_terminal:
                return None
            now = self.clock()
            if current and current.status is CheckpointStatus.IN_PROGRESS:
                updated_at = datetime.fromisoformat(current.updated_at)
                if updated_at.tzinfo is None:
                    raise CorruptCheckpointError("Checkpoint timestamps must include a timezone")
                if now - updated_at < self.stale_after:
                    return None
            claimed = DateCheckpoint(
                trading_date=key,
                status=CheckpointStatus.IN_PROGRESS,
                attempt_count=(current.attempt_count if current else 0) + 1,
                updated_at=now.isoformat(),
            )
            checkpoints[key] = claimed
            return claimed

        return self._locked_update(update)

    def complete(
        self,
        trading_date: date,
        *,
        request_id: str | None,
        landing_path: str,
        row_count: int,
        checksum: str,
    ) -> DateCheckpoint:
        if row_count < 0:
            raise ValueError("row_count cannot be negative")
        key = trading_date.isoformat()

        def update(checkpoints: dict[str, DateCheckpoint]) -> DateCheckpoint:
            current = checkpoints.get(key)
            if current is None or current.status is not CheckpointStatus.IN_PROGRESS:
                raise CheckpointError(f"Date {key} must be claimed before completion")
            completed = DateCheckpoint(
                trading_date=key,
                status=CheckpointStatus.NO_DATA if row_count == 0 else CheckpointStatus.COMPLETED,
                attempt_count=current.attempt_count,
                updated_at=self.clock().isoformat(),
                request_id=request_id,
                landing_path=landing_path,
                row_count=row_count,
                checksum=checksum,
            )
            checkpoints[key] = completed
            return completed

        return self._locked_update(update)

    def fail(self, trading_date: date, error: BaseException, *, retryable: bool) -> DateCheckpoint:
        key = trading_date.isoformat()

        def update(checkpoints: dict[str, DateCheckpoint]) -> DateCheckpoint:
            current = checkpoints.get(key)
            if current is None or current.status is not CheckpointStatus.IN_PROGRESS:
                raise CheckpointError(f"Date {key} must be claimed before failure")
            failed = DateCheckpoint(
                trading_date=key,
                status=(
                    CheckpointStatus.RETRYABLE_FAILURE
                    if retryable
                    else CheckpointStatus.TERMINAL_FAILURE
                ),
                attempt_count=current.attempt_count,
                updated_at=self.clock().isoformat(),
                error_type=type(error).__name__,
            )
            checkpoints[key] = failed
            return failed

        return self._locked_update(update)

    def snapshot(self) -> dict[str, DateCheckpoint]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_SH)
            return self._read_unlocked()
