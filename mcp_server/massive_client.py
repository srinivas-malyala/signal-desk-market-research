"""Rate-safe Massive Stocks REST client shared by ingestion and agent workloads.

Every physical HTTP attempt passes through a process-safe rolling-window limiter.
Credentials are accepted from the environment for local development or resolved
from the configured Databricks secret at runtime; they are never added to URLs.
"""

from __future__ import annotations

import base64
import email.utils
import fcntl
import json
import os
import random
import time
import uuid
from collections import deque
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import requests
from databricks.sdk import WorkspaceClient

BASE_URL = os.getenv("MASSIVE_API_BASE_URL", "https://api.massive.com").rstrip("/")
SECRET_SCOPE = os.getenv("MASSIVE_SECRET_SCOPE", "massive")
SECRET_KEY = os.getenv("MASSIVE_SECRET_KEY", "api-key")
DEFAULT_LIMITER_PATH = Path(os.getenv("MASSIVE_RATE_LIMIT_STATE_PATH", "/tmp/signal-desk-massive-rate.json"))
TRANSIENT_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class MassiveResponseError(RuntimeError):
    """Raised when Massive returns a successful but invalid response body."""


class RateLimiterStateError(RuntimeError):
    """Raised when quota state is corrupt so callers fail closed."""


@dataclass(frozen=True)
class RequestObservation:
    correlation_id: str
    massive_request_id: str | None
    status_code: int
    elapsed_ms: int
    bytes_received: int
    result_count: int | None
    attempt: int


@dataclass(frozen=True)
class MassiveResponse:
    payload: dict[str, Any]
    observation: RequestObservation


def _api_key(databricks_profile: str | None = None) -> str:
    if value := os.getenv("MASSIVE_API_KEY"):
        return value
    workspace = WorkspaceClient(profile=databricks_profile) if databricks_profile else WorkspaceClient()
    secret = workspace.secrets.get_secret(scope=SECRET_SCOPE, key=SECRET_KEY)
    if not secret.value:
        raise RuntimeError(f"Databricks secret {SECRET_SCOPE}/{SECRET_KEY} has no value")
    return base64.b64decode(secret.value).decode("utf-8")


class ProcessSafeRollingLimiter:
    """Coordinate a rolling quota through an advisory-locked JSON state file."""

    def __init__(
        self,
        state_path: Path = DEFAULT_LIMITER_PATH,
        limit: int = 4,
        window_seconds: float = 60.0,
        clock: Callable[[], float] = time.time,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if limit < 1 or window_seconds <= 0:
            raise ValueError("limit and window_seconds must be positive")
        self.state_path = state_path
        self.limit = limit
        self.window_seconds = window_seconds
        self.clock = clock
        self.sleeper = sleeper

    def acquire(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            with self.state_path.open("a+", encoding="utf-8") as state_file:
                fcntl.flock(state_file.fileno(), fcntl.LOCK_EX)
                state_file.seek(0)
                raw = state_file.read().strip()
                try:
                    released = json.loads(raw) if raw else []
                    if not isinstance(released, list) or not all(isinstance(value, (int, float)) for value in released):
                        raise ValueError
                except (json.JSONDecodeError, ValueError) as error:
                    raise RateLimiterStateError("Massive rate-limit state is corrupt; refusing API calls") from error

                now = self.clock()
                active = [float(value) for value in released if now - float(value) < self.window_seconds]
                if len(active) < self.limit:
                    active.append(now)
                    state_file.seek(0)
                    state_file.truncate()
                    json.dump(active, state_file)
                    state_file.flush()
                    os.fsync(state_file.fileno())
                    return
                wait_for = max(self.window_seconds - (now - min(active)), 0.001)
            self.sleeper(wait_for)


class MassiveClient:
    """Authenticated Massive client with quota-safe retries and response metadata."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = BASE_URL,
        timeout: int = 30,
        limiter: ProcessSafeRollingLimiter | None = None,
        max_retries: int = 3,
        backoff_factor: float = 0.6,
        jitter: float = 0.2,
        sleeper: Callable[[float], None] = time.sleep,
        random_source: Callable[[], float] = random.random,
        session: requests.Session | None = None,
        databricks_profile: str | None = None,
    ) -> None:
        if timeout <= 0 or max_retries < 0 or backoff_factor < 0 or jitter < 0:
            raise ValueError("timeout must be positive; retries, backoff, and jitter cannot be negative")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.limiter = limiter or ProcessSafeRollingLimiter()
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.jitter = jitter
        self.sleeper = sleeper
        self.random_source = random_source
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key or _api_key(databricks_profile)}",
                "User-Agent": "signal-desk/1.0",
            }
        )
        self.observations: deque[RequestObservation] = deque(maxlen=1000)

    def _retry_delay(self, response: requests.Response | None, retry_number: int) -> float:
        if response is not None and (retry_after := response.headers.get("Retry-After")):
            try:
                return max(float(retry_after), 0.0)
            except ValueError:
                parsed = email.utils.parsedate_to_datetime(retry_after)
                if parsed is not None:
                    return max((parsed - datetime.now(UTC)).total_seconds(), 0.0)
        return self.backoff_factor * (2 ** (retry_number - 1)) + self.jitter * self.random_source()

    def get_with_metadata(self, path_or_url: str, params: dict[str, Any] | None = None) -> MassiveResponse:
        url = path_or_url if path_or_url.startswith("http") else f"{self.base_url}{path_or_url}"
        correlation_id = str(uuid.uuid4())
        for attempt in range(1, self.max_retries + 2):
            self.limiter.acquire()
            started = time.perf_counter()
            response: requests.Response | None = None
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.timeout,
                    headers={"X-Correlation-ID": correlation_id},
                )
                elapsed_ms = round((time.perf_counter() - started) * 1000)
                result_count: int | None = None
                try:
                    candidate = response.json()
                    if isinstance(candidate, dict) and isinstance(candidate.get("results"), list):
                        result_count = len(candidate["results"])
                except requests.JSONDecodeError:
                    candidate = None
                observation = RequestObservation(
                    correlation_id=correlation_id,
                    massive_request_id=response.headers.get("X-Request-ID") or response.headers.get("x-request-id"),
                    status_code=response.status_code,
                    elapsed_ms=elapsed_ms,
                    bytes_received=len(response.content),
                    result_count=result_count,
                    attempt=attempt,
                )
                self.observations.append(observation)
                if response.status_code in TRANSIENT_STATUS_CODES and attempt <= self.max_retries:
                    self.sleeper(self._retry_delay(response, attempt))
                    continue
                response.raise_for_status()
                if not isinstance(candidate, dict):
                    raise MassiveResponseError(f"Massive returned invalid JSON for correlation {correlation_id}")
                return MassiveResponse(payload=candidate, observation=observation)
            except (requests.Timeout, requests.ConnectionError):
                if attempt > self.max_retries:
                    raise
                self.sleeper(self._retry_delay(response, attempt))
        raise AssertionError("retry loop exited unexpectedly")

    def get(self, path_or_url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.get_with_metadata(path_or_url, params).payload

    def metrics(self) -> dict[str, int]:
        values = list(self.observations)
        return {
            "http_attempts": len(values),
            "retries": sum(item.attempt > 1 for item in values),
            "bytes_received": sum(item.bytes_received for item in values),
            "elapsed_ms": sum(item.elapsed_ms for item in values),
        }

    def paginated_get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        max_items: int = 500,
    ) -> Iterator[dict[str, Any]]:
        """Yield ``results`` across Massive ``next_url`` pages."""
        url: str | None = path
        query = dict(params or {})
        emitted = 0
        while url and emitted < max_items:
            data = self.get(url, query)
            query = None
            results = data.get("results", [])
            if not isinstance(results, list):
                raise MassiveResponseError("Massive results must be a list")
            for item in results:
                if not isinstance(item, dict):
                    raise MassiveResponseError("Massive result items must be objects")
                yield item
                emitted += 1
                if emitted >= max_items:
                    return
            next_url = data.get("next_url")
            url = next_url if isinstance(next_url, str) and next_url else None

    def get_daily_market_summary(self, trading_date: date | str, include_otc: bool = True) -> MassiveResponse:
        value = trading_date if isinstance(trading_date, date) else date.fromisoformat(trading_date)
        response = self.get_with_metadata(
            f"/v2/aggs/grouped/locale/us/market/stocks/{value.isoformat()}",
            {"adjusted": "true", "include_otc": str(include_otc).lower()},
        )
        results = response.payload.get("results", [])
        if not isinstance(results, list) or not all(isinstance(item, dict) for item in results):
            raise MassiveResponseError("Massive grouped daily results must be a list of objects")
        return response

    def get_ticker_details(self, ticker: str) -> dict[str, Any]:
        result = self.get(f"/v3/reference/tickers/{ticker}").get("results", {})
        if not isinstance(result, dict):
            raise MassiveResponseError("Massive ticker details must be an object")
        return result

    def get_latest_price(self, ticker: str) -> dict[str, Any]:
        return self.get(f"/v2/aggs/ticker/{ticker}/prev")

    def get_snapshot(self, ticker: str) -> dict[str, Any]:
        result = self.get(f"/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}").get("ticker", {})
        if not isinstance(result, dict):
            raise MassiveResponseError("Massive ticker snapshot must be an object")
        return result

    def get_daily_bars(self, ticker: str, from_date: str, to_date: str, limit: int = 5000) -> list[dict]:
        data = self.get(
            f"/v2/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}",
            {"adjusted": "true", "sort": "asc", "limit": limit},
        )
        return self._list_results(data)

    def get_news(self, ticker: str, limit: int = 20, published_utc_gte: str | None = None) -> list[dict]:
        params: dict[str, Any] = {
            "ticker": ticker,
            "limit": min(max(limit, 1), 1000),
            "order": "desc",
            "sort": "published_utc",
        }
        if published_utc_gte:
            params["published_utc.gte"] = published_utc_gte
        return self._list_results(self.get("/v2/reference/news", params))

    def get_income_statements(self, ticker: str, limit: int = 4) -> list[dict]:
        data = self.get(
            "/stocks/financials/v1/income-statements",
            {"tickers": ticker, "limit": limit, "sort": "filing_date.desc"},
        )
        return self._list_results(data)

    def get_balance_sheets(self, ticker: str, limit: int = 4) -> list[dict]:
        data = self.get(
            "/stocks/financials/v1/balance-sheets",
            {"tickers": ticker, "limit": limit, "sort": "filing_date.desc"},
        )
        return self._list_results(data)

    def get_filings(self, ticker: str, limit: int = 10) -> list[dict]:
        data = self.get(
            "/stocks/filings/vX/index",
            {"ticker": ticker, "limit": limit, "sort": "filing_date.desc"},
        )
        return self._list_results(data)

    @staticmethod
    def _list_results(data: dict[str, Any]) -> list[dict]:
        results = data.get("results", [])
        if not isinstance(results, list) or not all(isinstance(item, dict) for item in results):
            raise MassiveResponseError("Massive results must be a list of objects")
        return results

    def observation_dicts(self) -> list[dict[str, Any]]:
        return [asdict(item) for item in self.observations]
