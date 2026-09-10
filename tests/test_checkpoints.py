from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from ingestion.checkpoints import (
    CheckpointStatus,
    CheckpointStore,
    CorruptCheckpointError,
    eligible_weekdays,
)


class FakeClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.value


def test_eligible_dates_exclude_weekends() -> None:
    assert eligible_weekdays(
        date(2026, 9, 4), date(2026, 9, 9), today=date(2026, 9, 10)
    ) == [
        date(2026, 9, 4),
        date(2026, 9, 7),
        date(2026, 9, 8),
        date(2026, 9, 9),
    ]


def test_eligible_dates_reject_future_and_out_of_history() -> None:
    with pytest.raises(ValueError, match="earlier than today"):
        eligible_weekdays(date(2026, 9, 9), date(2026, 9, 10), today=date(2026, 9, 10))
    with pytest.raises(ValueError, match="history window"):
        eligible_weekdays(date(2024, 9, 1), date(2026, 9, 9), today=date(2026, 9, 10))


def test_completed_and_no_data_dates_are_idempotent(tmp_path: Path) -> None:
    store = CheckpointStore(tmp_path / "checkpoints.json")
    populated = date(2026, 9, 8)
    holiday = date(2026, 9, 7)
    assert store.claim(populated)
    store.complete(
        populated,
        request_id="request-1",
        landing_path="market/trading_date=2026-09-08/response.json",
        row_count=10,
        checksum="abc",
    )
    assert store.claim(holiday)
    store.complete(
        holiday,
        request_id="request-2",
        landing_path="market/trading_date=2026-09-07/response.json",
        row_count=0,
        checksum="def",
    )
    assert store.claim(populated) is None
    assert store.claim(holiday) is None
    assert store.snapshot()[populated.isoformat()].status is CheckpointStatus.COMPLETED
    assert store.snapshot()[holiday.isoformat()].status is CheckpointStatus.NO_DATA


def test_stale_in_progress_date_can_be_reclaimed(tmp_path: Path) -> None:
    clock = FakeClock()
    store = CheckpointStore(tmp_path / "checkpoints.json", stale_after=timedelta(hours=1), clock=clock)
    target = date(2026, 9, 9)
    assert store.claim(target).attempt_count == 1
    assert store.claim(target) is None
    clock.value += timedelta(hours=2)
    assert store.claim(target).attempt_count == 2


def test_retryable_failure_can_resume_but_terminal_failure_requires_override(tmp_path: Path) -> None:
    store = CheckpointStore(tmp_path / "checkpoints.json")
    retryable = date(2026, 9, 8)
    terminal = date(2026, 9, 9)
    store.claim(retryable)
    store.fail(retryable, TimeoutError(), retryable=True)
    assert store.claim(retryable).attempt_count == 2
    store.claim(terminal)
    store.fail(terminal, ValueError(), retryable=False)
    assert store.claim(terminal) is None
    assert store.claim(terminal, retry_terminal=True).attempt_count == 2


def test_corrupt_checkpoint_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "checkpoints.json"
    path.write_text("not-json")
    with pytest.raises(CorruptCheckpointError):
        CheckpointStore(path).snapshot()


def test_interrupted_twenty_date_run_resumes_without_completed_dates(tmp_path: Path) -> None:
    path = tmp_path / "checkpoints.json"
    dates = eligible_weekdays(
        date(2026, 8, 13), date(2026, 9, 9), today=date(2026, 9, 10)
    )
    assert len(dates) == 20
    first_run = CheckpointStore(path)
    first_run.ensure_pending(dates)
    for index, trading_date in enumerate(dates[:10]):
        assert first_run.claim(trading_date)
        first_run.complete(
            trading_date,
            request_id=f"request-{index}",
            landing_path=f"market/trading_date={trading_date}/response.json",
            row_count=100,
            checksum=f"checksum-{index}",
        )

    resumed = CheckpointStore(path)
    claimed = [trading_date for trading_date in dates if resumed.claim(trading_date)]
    assert claimed == dates[10:]
