"""Responsible SEC EDGAR HTTP client with bounded retries and request pacing."""

from __future__ import annotations

import base64
import email.utils
import os
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import requests
from databricks.sdk import WorkspaceClient

SEC_DATA_BASE_URL = "https://data.sec.gov"
SEC_ARCHIVES_BASE_URL = "https://www.sec.gov/Archives/edgar/data"
TRANSIENT_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class SecResponseError(RuntimeError):
    """Raised when an SEC response does not match the requested contract."""


@dataclass(frozen=True)
class SecResponse:
    content: bytes
    content_type: str
    status_code: int
    elapsed_ms: int
    source_url: str


class ThreadSafeRollingLimiter:
    """Permit a conservative number of SEC requests in each rolling window."""

    def __init__(
        self,
        limit: int = 5,
        window_seconds: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if limit < 1 or window_seconds <= 0:
            raise ValueError("limit and window_seconds must be positive")
        self.limit = limit
        self.window_seconds = window_seconds
        self.clock = clock
        self.sleeper = sleeper
        self._released: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = self.clock()
                while self._released and now - self._released[0] >= self.window_seconds:
                    self._released.popleft()
                if len(self._released) < self.limit:
                    self._released.append(now)
                    return
                wait_for = max(self.window_seconds - (now - self._released[0]), 0.001)
            self.sleeper(wait_for)


def sec_user_agent(databricks_profile: str | None = None) -> str:
    """Resolve the identifying contact without accepting it as a CLI argument."""
    if value := os.getenv("SEC_USER_AGENT"):
        return value
    workspace = WorkspaceClient(profile=databricks_profile) if databricks_profile else WorkspaceClient()
    secret = workspace.secrets.get_secret(scope="sec", key="user-agent")
    if not secret.value:
        raise RuntimeError("Databricks secret sec/user-agent has no value")
    return base64.b64decode(secret.value).decode("utf-8")


class SecClient:
    """Fetch JSON and filing documents using SEC fair-access identification."""

    def __init__(
        self,
        user_agent: str | None = None,
        *,
        timeout: int = 30,
        max_retries: int = 3,
        limiter: ThreadSafeRollingLimiter | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        session: requests.Session | None = None,
        databricks_profile: str | None = None,
    ) -> None:
        identity = (user_agent or sec_user_agent(databricks_profile)).strip()
        if "@" not in identity or len(identity) < 8:
            raise ValueError("SEC User-Agent must contain an identifying contact email")
        if timeout <= 0 or max_retries < 0:
            raise ValueError("timeout must be positive and max_retries cannot be negative")
        self.user_agent = identity
        self.timeout = timeout
        self.max_retries = max_retries
        self.limiter = limiter or ThreadSafeRollingLimiter()
        self.sleeper = sleeper
        self._injected_session = session
        self._thread_local = threading.local()
        self.http_attempts = 0
        self.retries = 0

    def _session(self) -> requests.Session:
        if self._injected_session is not None:
            return self._injected_session
        if not hasattr(self._thread_local, "session"):
            session = requests.Session()
            session.headers.update(
                {
                    "User-Agent": self.user_agent,
                    "Accept-Encoding": "gzip, deflate",
                }
            )
            self._thread_local.session = session
        return self._thread_local.session

    def _retry_delay(self, response: requests.Response | None, retry_number: int) -> float:
        if response is not None and (retry_after := response.headers.get("Retry-After")):
            try:
                return max(float(retry_after), 0.0)
            except ValueError:
                parsed = email.utils.parsedate_to_datetime(retry_after)
                if parsed is not None:
                    return max((parsed - datetime.now(UTC)).total_seconds(), 0.0)
        return float(2 ** (retry_number - 1))

    def get_bytes(self, url: str) -> SecResponse:
        if not url.startswith(("https://data.sec.gov/", "https://www.sec.gov/")):
            raise ValueError("SEC client only permits official SEC HTTPS hosts")
        response: requests.Response | None = None
        for attempt in range(1, self.max_retries + 2):
            self.limiter.acquire()
            self.http_attempts += 1
            started = time.perf_counter()
            try:
                response = self._session().get(
                    url,
                    timeout=self.timeout,
                    headers={"User-Agent": self.user_agent},
                )
                elapsed_ms = round((time.perf_counter() - started) * 1000)
                if response.status_code in TRANSIENT_STATUS_CODES and attempt <= self.max_retries:
                    self.retries += 1
                    self.sleeper(self._retry_delay(response, attempt))
                    continue
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "application/octet-stream").split(";", 1)[0]
                return SecResponse(response.content, content_type, response.status_code, elapsed_ms, url)
            except (requests.Timeout, requests.ConnectionError):
                if attempt > self.max_retries:
                    raise
                self.retries += 1
                self.sleeper(self._retry_delay(response, attempt))
        raise AssertionError("retry loop exited unexpectedly")

    def get_json(self, url: str) -> tuple[dict[str, Any], SecResponse]:
        response = self.get_bytes(url)
        try:
            payload = requests.models.complexjson.loads(response.content)
        except ValueError as error:
            raise SecResponseError("SEC returned invalid JSON") from error
        if not isinstance(payload, dict):
            raise SecResponseError("SEC JSON response must be an object")
        return payload, response

    def get_submissions(self, cik: str) -> tuple[dict[str, Any], SecResponse]:
        return self.get_json(f"{SEC_DATA_BASE_URL}/submissions/CIK{cik}.json")

    def get_company_facts(self, cik: str) -> tuple[dict[str, Any], SecResponse]:
        return self.get_json(f"{SEC_DATA_BASE_URL}/api/xbrl/companyfacts/CIK{cik}.json")

    def get_filing_document(self, cik: str, accession: str, primary_document: str) -> SecResponse:
        compact_accession = accession.replace("-", "")
        url = f"{SEC_ARCHIVES_BASE_URL}/{int(cik)}/{compact_accession}/{primary_document}"
        return self.get_bytes(url)
