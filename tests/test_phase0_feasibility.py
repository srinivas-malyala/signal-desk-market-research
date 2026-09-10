from __future__ import annotations

from datetime import date

import pytest

from tools.phase0_feasibility import RollingWindowLimiter, project_volume, recent_weekdays


class FakeTime:
    def __init__(self) -> None:
        self.value = 0.0

    def clock(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


def test_limiter_releases_no_more_than_four_calls_per_window() -> None:
    fake = FakeTime()
    limiter = RollingWindowLimiter(
        limit=4,
        window_seconds=60,
        clock=fake.clock,
        sleeper=fake.sleep,
    )
    releases = []
    for _ in range(9):
        limiter.acquire()
        releases.append(fake.value)
    assert releases == [0.0, 0.0, 0.0, 0.0, 60.0, 60.0, 60.0, 60.0, 120.0]


def test_volume_projection_uses_observed_grouped_rows() -> None:
    result = project_volume([4300, 4400, 4500, 4200, 4600])
    assert result["average_rows_per_trading_date"] == 4400
    assert result["projected_trading_dates"] == 228
    assert result["projected_api_calls"] == 228
    assert result["minimum_api_minutes_at_configured_limit"] == 57


def test_volume_projection_rejects_empty_market() -> None:
    with pytest.raises(ValueError):
        project_volume([0, 0])


def test_recent_dates_exclude_weekends() -> None:
    assert recent_weekdays(3, today=date(2026, 9, 7)) == [
        date(2026, 9, 2),
        date(2026, 9, 3),
        date(2026, 9, 4),
    ]
