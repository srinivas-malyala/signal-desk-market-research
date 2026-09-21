from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).parents[1]
PATH = ROOT / "dashboard" / "analytics_client.py"
SPEC = importlib.util.spec_from_file_location("dashboard_analytics_client", PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_analytics_configuration_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABRICKS_WAREHOUSE_ID", raising=False)
    with pytest.raises(MODULE.AnalyticsUnavailableError):
        MODULE.DatabricksSQLAnalyticsClient.from_environment()
    monkeypatch.setenv("DATABRICKS_WAREHOUSE_ID", "warehouse123")
    monkeypatch.setenv("DATABRICKS_CATALOG", "bad-name")
    with pytest.raises(MODULE.AnalyticsUnavailableError):
        MODULE.DatabricksSQLAnalyticsClient.from_environment()


def test_snapshot_uses_bounded_gold_queries_and_detects_partial_state(monkeypatch: pytest.MonkeyPatch) -> None:
    fresh = datetime.now(UTC) - timedelta(seconds=30)
    rows = {
        "gold_daily_active_researchers": [("2026-09-21", 2, 4, fresh)],
        "gold_tool_usage_latency": [("2026-09-21", "semantic_research", 4, 100.0, fresh)],
    }
    descriptions = {
        "gold_daily_active_researchers": ["activity_date", "daily_active_researchers", "agent_invocations", "source_max_synced_at"],
        "gold_tool_usage_latency": ["activity_date", "tool_name", "invocation_count", "p95_duration_ms", "source_max_synced_at"],
    }
    statements = []

    class Cursor:
        description = []
        selected = ""
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def execute(self, statement):
            statements.append(statement)
            self.selected = next((name for name in rows if name in statement), "")
            self.description = [(name,) for name in descriptions.get(self.selected, ["activity_date"])]
        def fetchall(self): return rows.get(self.selected, [])
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def cursor(self): return Cursor()
    fake_sql = SimpleNamespace(connect=lambda **_kwargs: Connection())
    fake_config = SimpleNamespace(host="https://workspace.example", authenticate=lambda: {})
    monkeypatch.setitem(sys.modules, "databricks.sql", fake_sql)
    monkeypatch.setattr("databricks.sdk.core.Config", lambda: fake_config)
    report = MODULE.DatabricksSQLAnalyticsClient("warehouse123").snapshot()
    assert report["state"] == "partial"
    assert report["execution_identity"] == "Databricks App service principal"
    assert len(statements) == 5
    assert all("LIMIT" in statement and "`bootcamp_students`.`student_sri`.`gold_" in statement for statement in statements)


def test_snapshot_detects_stale_data(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 9, 21, tzinfo=UTC)
    datasets = {name: [{"value": 1}] for name in ("daily_active", "tool_usage", "error_rate")}
    assert MODULE.analytics_state({}, None, 60, now) == ("empty", None)
    assert MODULE.analytics_state({"one": [{}], "two": []}, None, 60, now)[0] == "partial"
    state, age = MODULE.analytics_state(datasets, now - timedelta(hours=2), 60, now)
    assert state == "stale"
    assert age == 7200
