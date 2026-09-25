"""Bounded SQL Warehouse reads for governed historical market data."""

from __future__ import annotations

import os
from typing import Any

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementParameterListItem

from shared.databricks_auth import hosting_mode, workspace_client

NUMERIC_FIELDS = frozenset(
    {
        "open",
        "high",
        "low",
        "close",
        "vwap",
        "volume",
        "transactions",
        "daily_return",
        "annualized_volatility_20d",
    }
)


def _workspace(access_token: str | None = None) -> WorkspaceClient:
    if hosting_mode() == "render":
        return workspace_client()
    if access_token:
        host = os.environ.get("DATABRICKS_HOST")
        if not host:
            raise ValueError("DATABRICKS_HOST is required for on-behalf-of-user SQL.")
        return WorkspaceClient(host=host, token=access_token)
    return workspace_client()


def fetch_market_bars(
    ticker: str,
    start_date: str,
    end_date: str,
    *,
    access_token: str | None = None,
    workspace: WorkspaceClient | None = None,
) -> list[dict[str, Any]]:
    warehouse_id = os.environ.get("DATA_WORKSPACE_WAREHOUSE_ID") or os.environ.get("DATABRICKS_WAREHOUSE_ID")
    if not warehouse_id:
        raise RuntimeError("DATABRICKS_WAREHOUSE_ID is not configured.")
    catalog = os.environ.get("DATABRICKS_CATALOG", "bootcamp_students")
    schema = os.environ.get("DATABRICKS_SCHEMA", "student_sri")
    response = (workspace or _workspace(access_token)).statement_execution.execute_statement(
        warehouse_id=warehouse_id,
        catalog=catalog,
        schema=schema,
        wait_timeout="30s",
        row_limit=370,
        statement="""SELECT CAST(s.trading_date AS STRING) AS date,
          CAST(s.open AS DOUBLE) AS open, CAST(s.high AS DOUBLE) AS high,
          CAST(s.low AS DOUBLE) AS low, CAST(s.close AS DOUBLE) AS close,
          CAST(s.vwap AS DOUBLE) AS vwap, CAST(s.volume AS DOUBLE) AS volume,
          CAST(s.transactions AS DOUBLE) AS transactions,
          CAST(g.daily_return AS DOUBLE) AS daily_return,
          CAST(g.annualized_volatility_20d AS DOUBLE) AS annualized_volatility_20d,
          s.source_request_id
        FROM silver_market_bars s
        LEFT JOIN gold_stock_performance g USING(ticker,trading_date)
        WHERE s.ticker=:ticker AND s.trading_date BETWEEN :start_date AND :end_date
        ORDER BY s.trading_date""",
        parameters=[
            StatementParameterListItem(name="ticker", value=ticker, type="STRING"),
            StatementParameterListItem(name="start_date", value=start_date, type="DATE"),
            StatementParameterListItem(name="end_date", value=end_date, type="DATE"),
        ],
    )
    columns = [column.name for column in (getattr(getattr(response.manifest, "schema", None), "columns", None) or [])]
    values = getattr(response.result, "data_array", None) or []
    rows = []
    for raw in values:
        row = dict(zip(columns, raw, strict=False))
        for field in NUMERIC_FIELDS:
            if row.get(field) is not None:
                row[field] = float(row[field])
        rows.append(row)
    return rows
