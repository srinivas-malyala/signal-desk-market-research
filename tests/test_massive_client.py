from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from mcp_server.massive_client import (
    MassiveClient,
    MassiveResponseError,
    ProcessSafeRollingLimiter,
    RateLimiterStateError,
)


class FakeTime:
    def __init__(self) -> None:
        self.value = 1_000.0

    def clock(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


def response(status: int, payload, headers: dict[str, str] | None = None) -> Mock:
    value = Mock(spec=requests.Response)
    value.status_code = status
    value.headers = headers or {}
    value.content = json.dumps(payload).encode() if payload is not None else b"not-json"
    if payload is None:
        value.json.side_effect = requests.JSONDecodeError("invalid", "x", 0)
    else:
        value.json.return_value = payload
    if status >= 400:
        value.raise_for_status.side_effect = requests.HTTPError(response=value)
    return value


def test_limiter_releases_no_more_than_four_attempts_per_rolling_minute(tmp_path: Path) -> None:
    fake = FakeTime()
    limiter = ProcessSafeRollingLimiter(tmp_path / "quota.json", clock=fake.clock, sleeper=fake.sleep)
    released = []
    for _ in range(9):
        limiter.acquire()
        released.append(fake.value)
    assert released == [1000.0] * 4 + [1060.0] * 4 + [1120.0]


def test_limiter_instances_share_the_same_state_file(tmp_path: Path) -> None:
    fake = FakeTime()
    path = tmp_path / "quota.json"
    first = ProcessSafeRollingLimiter(path, limit=1, window_seconds=60, clock=fake.clock, sleeper=fake.sleep)
    second = ProcessSafeRollingLimiter(path, limit=1, window_seconds=60, clock=fake.clock, sleeper=fake.sleep)
    first.acquire()
    second.acquire()
    assert fake.value == 1060.0


def test_concurrent_callers_share_one_allowance(tmp_path: Path) -> None:
    class QuotaWouldBlock(RuntimeError):
        pass

    path = tmp_path / "quota.json"
    first = ProcessSafeRollingLimiter(
        path, clock=lambda: 1000.0, sleeper=lambda _seconds: (_ for _ in ()).throw(QuotaWouldBlock())
    )
    second = ProcessSafeRollingLimiter(
        path, clock=lambda: 1000.0, sleeper=lambda _seconds: (_ for _ in ()).throw(QuotaWouldBlock())
    )
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit((first if index % 2 else second).acquire) for index in range(8)]
    outcomes = []
    for future in futures:
        try:
            future.result()
            outcomes.append("released")
        except QuotaWouldBlock:
            outcomes.append("blocked")
    assert outcomes.count("released") == 4
    assert outcomes.count("blocked") == 4


def test_limiter_fails_closed_on_corrupt_state(tmp_path: Path) -> None:
    path = tmp_path / "quota.json"
    path.write_text("not-json")
    with pytest.raises(RateLimiterStateError):
        ProcessSafeRollingLimiter(path).acquire()


def test_every_retry_is_rate_limited_and_retry_after_is_honored() -> None:
    limiter = Mock()
    session = Mock(spec=requests.Session)
    session.headers = {}
    session.get.side_effect = [
        response(429, {"status": "ERROR"}, {"Retry-After": "7"}),
        response(200, {"results": [{"T": "AAPL"}]}, {"X-Request-ID": "massive-1"}),
    ]
    sleeps = []
    client = MassiveClient(
        api_key="fixture-key",
        limiter=limiter,
        session=session,
        sleeper=sleeps.append,
        jitter=0,
    )
    result = client.get("/example")
    assert result["results"][0]["T"] == "AAPL"
    assert limiter.acquire.call_count == 2
    assert sleeps == [7.0]
    assert client.metrics()["retries"] == 1


@pytest.mark.parametrize("status", [401, 403, 404])
def test_terminal_http_errors_are_not_retried(status: int) -> None:
    limiter = Mock()
    session = Mock(spec=requests.Session)
    session.headers = {}
    session.get.return_value = response(status, {"status": "ERROR"})
    client = MassiveClient(api_key="fixture-key", limiter=limiter, session=session)
    with pytest.raises(requests.HTTPError):
        client.get("/terminal")
    assert limiter.acquire.call_count == 1
    assert session.get.call_count == 1


def test_timeout_retry_is_rate_limited() -> None:
    limiter = Mock()
    session = Mock(spec=requests.Session)
    session.headers = {}
    session.get.side_effect = [requests.Timeout("timed out"), response(200, {"results": []})]
    sleeps = []
    client = MassiveClient(
        api_key="fixture-key",
        limiter=limiter,
        session=session,
        sleeper=sleeps.append,
        jitter=0,
    )
    assert client.get("/eventual")["results"] == []
    assert limiter.acquire.call_count == 2
    assert sleeps == [0.6]


def test_grouped_daily_method_preserves_required_parameters() -> None:
    client = MassiveClient(api_key="fixture-key", limiter=Mock())
    envelope = Mock(payload={"results": []})
    client.get_with_metadata = Mock(return_value=envelope)
    assert client.get_daily_market_summary(date(2026, 9, 9)) is envelope
    client.get_with_metadata.assert_called_once_with(
        "/v2/aggs/grouped/locale/us/market/stocks/2026-09-09",
        {"adjusted": "true", "include_otc": "true"},
    )


def test_grouped_daily_empty_results_are_valid_for_market_holidays() -> None:
    client = MassiveClient(api_key="fixture-key", limiter=Mock())
    envelope = Mock(payload={"status": "OK", "results": []})
    client.get_with_metadata = Mock(return_value=envelope)
    assert client.get_daily_market_summary("2026-09-07") is envelope


def test_invalid_json_raises_safe_error_without_api_key() -> None:
    session = Mock(spec=requests.Session)
    session.headers = {}
    session.get.return_value = response(200, None)
    client = MassiveClient(api_key="highly-secret-key", limiter=Mock(), session=session, max_retries=0)
    with pytest.raises(MassiveResponseError) as captured:
        client.get("/broken")
    assert "highly-secret-key" not in str(captured.value)


def test_non_list_results_are_rejected() -> None:
    client = MassiveClient(api_key="fixture-key", limiter=Mock())
    with pytest.raises(MassiveResponseError):
        client._list_results({"results": {"ticker": "AAPL"}})
