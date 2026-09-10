"""Run reproducible, credential-safe Phase 0 feasibility checks.

Credentials are read from environment variables, never command-line arguments.
Databricks checks require an explicitly supplied profile.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

MASSIVE_BASE_URL = os.getenv("MASSIVE_API_BASE_URL", "https://api.massive.com").rstrip("/")
SEC_BASE_URL = "https://data.sec.gov"
SAFE_RESPONSE_HEADERS = {"content-length", "content-type", "date", "retry-after", "x-request-id"}


@dataclass(frozen=True)
class HttpObservation:
    url_path: str
    status: int
    elapsed_ms: int
    bytes_received: int
    row_count: int | None
    safe_headers: dict[str, str]


class RollingWindowLimiter:
    """Release at most limit calls during any rolling window."""

    def __init__(
        self,
        limit: int = 4,
        window_seconds: float = 60.0,
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

    def acquire(self) -> None:
        now = self.clock()
        while self._released and now - self._released[0] >= self.window_seconds:
            self._released.popleft()
        if len(self._released) >= self.limit:
            wait_for = self.window_seconds - (now - self._released[0])
            self.sleeper(max(wait_for, 0.0))
            now = self.clock()
            while self._released and now - self._released[0] >= self.window_seconds:
                self._released.popleft()
        self._released.append(now)


def recent_weekdays(count: int, today: date | None = None) -> list[date]:
    cursor = (today or date.today()) - timedelta(days=1)
    values: list[date] = []
    while len(values) < count:
        if cursor.weekday() < 5:
            values.append(cursor)
        cursor -= timedelta(days=1)
    return sorted(values)


def project_volume(
    row_counts: list[int],
    target_rows: int = 1_000_001,
    calls_per_minute: int = 4,
) -> dict:
    observed = [count for count in row_counts if count >= 0]
    if not observed:
        raise ValueError("at least one observed row count is required")
    average = sum(observed) / len(observed)
    if average <= 0:
        raise ValueError("observed responses contain no rows")
    trading_dates = math.ceil(target_rows / average)
    return {
        "observed_dates": len(observed),
        "observed_rows": sum(observed),
        "average_rows_per_trading_date": round(average, 2),
        "target_rows": target_rows,
        "projected_trading_dates": trading_dates,
        "projected_api_calls": trading_dates,
        "minimum_api_minutes_at_configured_limit": round(trading_dates / calls_per_minute, 2),
        "configured_calls_per_minute": calls_per_minute,
    }


def _json_request(
    url: str,
    headers: dict[str, str],
    timeout: int = 45,
) -> tuple[dict, HttpObservation]:
    started = time.monotonic()
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload_bytes = response.read()
        payload = json.loads(payload_bytes)
        safe_headers = {
            key.lower(): value
            for key, value in response.headers.items()
            if key.lower() in SAFE_RESPONSE_HEADERS
        }
        observation = HttpObservation(
            url_path=urllib.parse.urlsplit(url).path,
            status=response.status,
            elapsed_ms=round((time.monotonic() - started) * 1000),
            bytes_received=len(payload_bytes),
            row_count=len(payload.get("results", [])) if isinstance(payload.get("results"), list) else None,
            safe_headers=safe_headers,
        )
        return payload, observation


def check_massive(api_key: str, dates: list[date]) -> dict:
    limiter = RollingWindowLimiter(limit=4, window_seconds=60)
    observations: list[HttpObservation] = []
    failures: list[dict[str, str]] = []
    for trading_date in dates:
        limiter.acquire()
        query = urllib.parse.urlencode({"adjusted": "true", "include_otc": "true"})
        url = (
            f"{MASSIVE_BASE_URL}/v2/aggs/grouped/locale/us/market/stocks/"
            f"{trading_date.isoformat()}?{query}"
        )
        try:
            _, observation = _json_request(
                url,
                {
                    "Authorization": f"Bearer {api_key}",
                    "User-Agent": "signal-desk-feasibility/1.0",
                },
            )
            observations.append(observation)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            failures.append({"date": trading_date.isoformat(), "error_type": type(error).__name__})
    row_counts = [item.row_count or 0 for item in observations]
    return {
        "status": "passed" if observations and not failures else "failed",
        "endpoint": "/v2/aggs/grouped/locale/us/market/stocks/{date}",
        "include_otc": True,
        "observations": [asdict(item) for item in observations],
        "failures": failures,
        "volume_projection": project_volume(row_counts) if any(row_counts) else None,
    }


def check_sec(user_agent: str) -> dict:
    headers = {
        "User-Agent": user_agent,
        "Host": "data.sec.gov",
    }
    urls = {
        "submissions": f"{SEC_BASE_URL}/submissions/CIK0000320193.json",
        "company_facts": f"{SEC_BASE_URL}/api/xbrl/companyfacts/CIK0000320193.json",
    }
    observations: dict[str, dict] = {}
    for name, url in urls.items():
        payload, observation = _json_request(url, headers)
        observations[name] = {
            **asdict(observation),
            "entity_name": payload.get("name") or payload.get("entityName"),
            "cik": str(payload.get("cik", "")).zfill(10),
        }
    return {"status": "passed", "observations": observations}


def _databricks_command(profile: str, arguments: list[str]) -> dict:
    command = ["databricks", *arguments, "--profile", profile, "--output", "json"]
    result = subprocess.run(command, text=True, capture_output=True, check=False, timeout=60)
    return {
        "command": "databricks " + " ".join(arguments) + " --profile <selected-profile>",
        "status": "passed" if result.returncode == 0 else "failed",
        "return_code": result.returncode,
        "error": result.stderr.strip()[-1000:] if result.returncode else None,
    }


def check_databricks(profile: str) -> dict:
    checks = [
        _databricks_command(profile, ["current-user", "me"]),
        _databricks_command(profile, ["apps", "list"]),
        _databricks_command(profile, ["pipelines", "list"]),
        _databricks_command(profile, ["postgres", "list-projects"]),
    ]
    return {
        "status": "passed" if all(item["status"] == "passed" for item in checks) else "failed",
        "profile": profile,
        "checks": checks,
        "lakebase_cdf_crud": {
            "status": "not_run",
            "reason": (
                "Requires user selection of a Lakebase project/branch/database "
                "and approval of a disposable row test."
            ),
        },
    }


def build_report(profile: str | None, dates: list[date]) -> dict:
    report: dict = {
        "report_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "credentials_recorded": False,
        "massive": {"status": "blocked", "reason": "MASSIVE_API_KEY is not set"},
        "sec": {"status": "blocked", "reason": "SEC_USER_AGENT is not set"},
        "databricks": {"status": "blocked", "reason": "No explicit --profile was supplied"},
    }
    if api_key := os.getenv("MASSIVE_API_KEY"):
        report["massive"] = check_massive(api_key, dates)
    if user_agent := os.getenv("SEC_USER_AGENT"):
        report["sec"] = check_sec(user_agent)
    if profile:
        report["databricks"] = check_databricks(profile)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", help="Explicit Databricks CLI profile; never inferred")
    parser.add_argument(
        "--date",
        action="append",
        dest="dates",
        help="Trading date YYYY-MM-DD; repeat up to five times",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/phase0/feasibility.json"),
    )
    args = parser.parse_args()
    dates = [date.fromisoformat(value) for value in args.dates] if args.dates else recent_weekdays(5)
    if not 1 <= len(dates) <= 5:
        parser.error("provide between one and five dates")
    report = build_report(args.profile, dates)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"Wrote sanitized feasibility evidence to {args.output}")
    return 0 if all(report[key]["status"] == "passed" for key in ("massive", "sec", "databricks")) else 2


if __name__ == "__main__":
    raise SystemExit(main())
