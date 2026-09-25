"""Bounded SQL Warehouse reader for privacy-safe Phase 6 Gold metrics."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from shared.databricks_auth import DatabricksAuthConfigurationError, sql_connection

IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")
MAX_RESPONSE_BYTES = 256_000


class AnalyticsUnavailableError(RuntimeError):
    """Analytics could not be queried safely."""


class AnalyticsClient(Protocol):
    def snapshot(self) -> dict[str, Any]: ...


def _identifier(value: str, name: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise AnalyticsUnavailableError(f"{name} is invalid")
    return value


def _json_value(value: Any) -> Any:
    return value.isoformat() if isinstance(value, datetime) else value


def analytics_state(
    datasets: dict[str, list[dict[str, Any]]],
    freshness: str | datetime | None,
    stale_after_seconds: int,
    now: datetime | None = None,
) -> tuple[str, float | None]:
    nonempty = sum(bool(rows) for rows in datasets.values())
    state = "empty" if nonempty == 0 else "partial" if nonempty < len(datasets) else "ready"
    age_seconds = None
    if freshness:
        parsed = freshness if isinstance(freshness, datetime) else datetime.fromisoformat(str(freshness).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        age_seconds = max(((now or datetime.now(UTC)) - parsed).total_seconds(), 0)
        if age_seconds > stale_after_seconds:
            state = "stale"
    return state, age_seconds


@dataclass(frozen=True)
class DatabricksSQLAnalyticsClient:
    warehouse_id: str
    catalog: str = "bootcamp_students"
    schema: str = "student_sri"
    stale_after_seconds: int = 3600

    @classmethod
    def from_environment(cls) -> DatabricksSQLAnalyticsClient:
        warehouse = os.getenv("DATABRICKS_WAREHOUSE_ID", "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{8,128}", warehouse):
            raise AnalyticsUnavailableError("SQL warehouse is not configured")
        try:
            stale_after = int(os.getenv("ANALYTICS_STALE_AFTER_SECONDS", "3600"))
        except ValueError as exc:
            raise AnalyticsUnavailableError("Analytics freshness threshold is invalid") from exc
        if not 60 <= stale_after <= 86_400:
            raise AnalyticsUnavailableError("Analytics freshness threshold is invalid")
        return cls(
            warehouse_id=warehouse,
            catalog=_identifier(os.getenv("DATABRICKS_CATALOG", "bootcamp_students"), "catalog"),
            schema=_identifier(os.getenv("DATABRICKS_SCHEMA", "student_sri"), "schema"),
            stale_after_seconds=stale_after,
        )

    def _table(self, name: str) -> str:
        return f"`{self.catalog}`.`{self.schema}`.`{_identifier(name, 'table')}`"

    def snapshot(self) -> dict[str, Any]:
        try:
            connection = sql_connection(self.warehouse_id)
            queries = {
                "daily_active": f"SELECT * FROM {self._table('gold_daily_active_researchers')} ORDER BY activity_date DESC LIMIT 30",
                "tool_usage": f"SELECT * FROM {self._table('gold_tool_usage_latency')} ORDER BY activity_date DESC, invocation_count DESC LIMIT 200",
                "error_rate": f"SELECT * FROM {self._table('gold_agent_error_rate')} ORDER BY activity_date DESC LIMIT 30",
                "watchlist_changes": f"SELECT * FROM {self._table('gold_watchlist_changes')} ORDER BY activity_date DESC, action_type LIMIT 100",
                "research_saves": f"SELECT * FROM {self._table('gold_research_saves')} ORDER BY activity_date DESC, research_type, action_type LIMIT 100",
            }
            datasets: dict[str, list[dict[str, Any]]] = {}
            with connection:
                for name, statement in queries.items():
                    with connection.cursor() as cursor:
                        cursor.execute(statement)
                        columns = [description[0] for description in cursor.description]
                        datasets[name] = [
                            {column: _json_value(value) for column, value in zip(columns, row, strict=True)}
                            for row in cursor.fetchall()
                        ]
        except AnalyticsUnavailableError:
            raise
        except DatabricksAuthConfigurationError as exc:
            raise AnalyticsUnavailableError("Usage analytics are temporarily unavailable") from exc
        except Exception as exc:
            raise AnalyticsUnavailableError("Usage analytics are temporarily unavailable") from exc

        freshness_values = [
            row.get("source_max_synced_at")
            for rows in datasets.values()
            for row in rows
            if row.get("source_max_synced_at")
        ]
        freshness = max(freshness_values, default=None)
        state, age_seconds = analytics_state(datasets, freshness, self.stale_after_seconds)
        result = {
            "status": "success",
            "state": state,
            "datasets": datasets,
            "source_max_synced_at": freshness,
            "freshness_age_seconds": round(age_seconds, 1) if age_seconds is not None else None,
            "execution_identity": "least-privilege Databricks service principal",
            "source": "Phase 6 Gold usage tables via Databricks SQL Warehouse",
        }
        if len(json.dumps(result, default=str).encode("utf-8")) > MAX_RESPONSE_BYTES:
            raise AnalyticsUnavailableError("Usage analytics response exceeded the allowed size")
        return result
