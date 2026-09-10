from __future__ import annotations

import json
from unittest.mock import Mock

import pytest
import requests

from ingestion.sec_client import SecClient, SecResponseError, ThreadSafeRollingLimiter


class FakeTime:
    def __init__(self) -> None:
        self.value = 100.0

    def clock(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


def response(status: int, payload: object, content_type: str = "application/json") -> Mock:
    value = Mock(spec=requests.Response)
    value.status_code = status
    value.headers = {"Content-Type": content_type}
    value.content = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    if status >= 400:
        value.raise_for_status.side_effect = requests.HTTPError(response=value)
    return value


def test_sec_limiter_is_conservatively_bounded() -> None:
    fake = FakeTime()
    limiter = ThreadSafeRollingLimiter(limit=2, window_seconds=1, clock=fake.clock, sleeper=fake.sleep)
    released = []
    for _ in range(5):
        limiter.acquire()
        released.append(fake.value)
    assert released == [100.0, 100.0, 101.0, 101.0, 102.0]


def test_client_identifies_every_request_and_limits_retries() -> None:
    session = Mock(spec=requests.Session)
    session.get.side_effect = [
        response(429, {"message": "slow down"}),
        response(200, {"cik": "0000320193"}),
    ]
    limiter = Mock()
    sleeps: list[float] = []
    client = SecClient(
        "Signal Desk Capstone student@example.com",
        session=session,
        limiter=limiter,
        sleeper=sleeps.append,
    )

    payload, _ = client.get_submissions("0000320193")

    assert payload["cik"] == "0000320193"
    assert limiter.acquire.call_count == 2
    assert client.http_attempts == 2
    assert client.retries == 1
    assert sleeps == [1.0]
    assert session.get.call_args.kwargs["headers"]["User-Agent"].endswith("@example.com")


def test_client_rejects_non_sec_hosts_and_invalid_json() -> None:
    client = SecClient("Signal Desk student@example.com", session=Mock(), limiter=Mock())
    with pytest.raises(ValueError, match="official SEC"):
        client.get_bytes("https://example.com/document")

    client._injected_session.get.return_value = response(200, b"<html>not json</html>", "text/html")
    with pytest.raises(SecResponseError, match="invalid JSON"):
        client.get_json("https://data.sec.gov/submissions/CIK0000320193.json")


def test_terminal_missing_document_is_not_retried() -> None:
    session = Mock(spec=requests.Session)
    session.get.return_value = response(404, {"message": "not found"})
    client = SecClient("Signal Desk student@example.com", session=session, limiter=Mock())
    with pytest.raises(requests.HTTPError):
        client.get_filing_document("0000320193", "0000320193-25-000079", "aapl.htm")
    assert session.get.call_count == 1
