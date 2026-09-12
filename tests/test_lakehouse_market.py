from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

MCP_ROOT = Path(__file__).parents[1] / "mcp_server"
sys.path.insert(0, str(MCP_ROOT))

from lakehouse_market import fetch_market_bars  # noqa: E402


def test_market_history_uses_bounded_parameterized_warehouse_query(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABRICKS_WAREHOUSE_ID", "warehouse-id")
    workspace = Mock()
    columns = ["date", "open", "close", "volume", "daily_return", "source_request_id"]
    workspace.statement_execution.execute_statement.return_value = SimpleNamespace(
        manifest=SimpleNamespace(
            schema=SimpleNamespace(columns=[SimpleNamespace(name=column) for column in columns])
        ),
        result=SimpleNamespace(data_array=[["2026-09-10", "100", "110", "2000", "0.1", "request-id"]]),
    )
    rows = fetch_market_bars("AAPL", "2026-09-01", "2026-09-10", workspace=workspace)
    assert rows == [
        {
            "date": "2026-09-10",
            "open": 100.0,
            "close": 110.0,
            "volume": 2000.0,
            "daily_return": 0.1,
            "source_request_id": "request-id",
        }
    ]
    call = workspace.statement_execution.execute_statement.call_args.kwargs
    assert call["warehouse_id"] == "warehouse-id"
    assert call["row_limit"] == 370
    assert ":ticker" in call["statement"] and "AAPL" not in call["statement"]
    assert {parameter.name: parameter.value for parameter in call["parameters"]} == {
        "ticker": "AAPL",
        "start_date": "2026-09-01",
        "end_date": "2026-09-10",
    }
