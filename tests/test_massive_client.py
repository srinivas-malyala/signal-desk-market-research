from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from mcp_server import massive_client
from mcp_server.massive_client import (
    LakebaseRollingLimiter,
    MassiveClient,
    MassiveResponseError,
    ProcessSafeRollingLimiter,
    RateLimiterStateError,
    build_rate_limiter,
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
    audit = [json.loads(path.read_text()) for path in sorted((tmp_path / "quota_audit").glob("*.json"))]
    assert [item["acquired_at_epoch"] for item in audit] == released
    assert all(item["limit"] == 4 and item["window_seconds"] == 60 for item in audit)
    assert len({path.name for path in (tmp_path / "quota_audit").glob("*.json")}) == 9


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


class SharedLakebaseState:
    def __init__(self) -> None:
        self.now = 1_000.0
        self.attempts: list[float] = []
        self.commits = 0

    @contextmanager
    def connection(self):
        state = self

        class Cursor:
            result = None

            def __enter__(self):
                return self

            def __exit__(self, *_args) -> None:
                return None

            def execute(self, statement, params=None) -> None:
                normalized = " ".join(str(statement).split())
                if "SELECT COUNT(*) AS active_count" in normalized:
                    window = float(params[0])
                    active = [value for value in state.attempts if value > state.now - window]
                    wait = min(active) + window - state.now if active else 0.001
                    self.result = {"active_count": len(active), "wait_seconds": max(wait, 0.001)}
                elif "INSERT INTO" in normalized:
                    state.attempts.append(state.now)

            def fetchone(self):
                return self.result

        class Connection:
            def cursor(self):
                return Cursor()

            def commit(self) -> None:
                state.commits += 1

        yield Connection()

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def test_lakebase_limiter_coordinates_independent_hosts() -> None:
    state = SharedLakebaseState()
    first = LakebaseRollingLimiter(
        state.connection,
        "bootcamp_students.massive_api_attempts_srini",
        sleeper=state.sleep,
        requester="job",
    )
    second = LakebaseRollingLimiter(
        state.connection,
        "bootcamp_students.massive_api_attempts_srini",
        sleeper=state.sleep,
        requester="mcp",
    )
    released = []
    for limiter in (first, second, first, second, first):
        limiter.acquire()
        released.append(state.now)
    assert released == [1000.0, 1000.0, 1000.0, 1000.0, 1060.0]
    assert state.commits == 6


def test_lakebase_limiter_fails_closed_when_store_is_unavailable() -> None:
    @contextmanager
    def unavailable():
        raise RuntimeError("database offline")
        yield

    limiter = LakebaseRollingLimiter(unavailable, "bootcamp_students.massive_api_attempts_srini")
    with pytest.raises(RateLimiterStateError, match="refusing API calls"):
        limiter.acquire()


def test_rate_limiter_backend_selection_is_explicit(tmp_path: Path) -> None:
    assert isinstance(build_rate_limiter("process", state_path=tmp_path / "quota.json"), ProcessSafeRollingLimiter)
    with pytest.raises(ValueError, match="process.*lakebase"):
        build_rate_limiter("unknown")


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


def test_secret_lookup_can_use_an_explicit_databricks_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    secret = Mock(value="Zml4dHVyZS1rZXk=")
    workspace = Mock()
    workspace.secrets.get_secret.return_value = secret
    constructor = Mock(return_value=workspace)
    monkeypatch.setattr(massive_client, "WorkspaceClient", constructor)
    assert massive_client._api_key("selected") == "fixture-key"
    constructor.assert_called_once_with(profile="selected")
