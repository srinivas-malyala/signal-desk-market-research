from __future__ import annotations

from datetime import date

import pytest

from tools import phase0_feasibility
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


def test_workspace_checks_use_current_pipeline_cli_command(monkeypatch: pytest.MonkeyPatch) -> None:
    invoked = []

    def fake_command(_profile: str, arguments: list[str]) -> dict:
        invoked.append(arguments)
        return {"status": "passed"}

    monkeypatch.setattr(phase0_feasibility, "_databricks_command", fake_command)
    result = phase0_feasibility.check_databricks("selected")
    assert ["pipelines", "list-pipelines"] in invoked
    assert result["status"] == "passed"


def test_report_can_read_massive_key_from_selected_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    monkeypatch.setattr(phase0_feasibility, "get_databricks_secret", lambda *_args: "in-memory-key")
    monkeypatch.setattr(phase0_feasibility, "check_massive", lambda key, _dates: {"status": "passed", "key_seen": key})
    monkeypatch.setattr(phase0_feasibility, "check_databricks", lambda _profile: {"status": "passed"})
    report = phase0_feasibility.build_report(
        "selected",
        [date(2026, 9, 9)],
        massive_secret_scope="massive",
    )
    assert report["massive"] == {"status": "passed", "key_seen": "in-memory-key"}
