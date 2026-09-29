"""Publish a narrow CDF-enabled Delta table for Lakebase market serving."""

from __future__ import annotations

import argparse
import json
import re
from typing import Any

SILVER_TABLE = "silver_market_bars"
GOLD_TABLE = "gold_stock_performance"
TARGET_TABLE = "market_history_serving"
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _qualified_name(catalog: str, schema: str, table: str) -> str:
    if not all(_IDENTIFIER.fullmatch(part) for part in (catalog, schema, table)):
        raise ValueError("Catalog, schema, and table names must be simple SQL identifiers")
    return ".".join(f"`{part}`" for part in (catalog, schema, table))


def serving_source_sql(catalog: str, schema: str) -> str:
    silver = _qualified_name(catalog, schema, SILVER_TABLE)
    gold = _qualified_name(catalog, schema, GOLD_TABLE)
    return f"""SELECT s.ticker, s.trading_date,
              s.open, s.high, s.low, s.close, s.vwap, s.volume, s.transactions,
              g.daily_return, g.annualized_volatility_20d,
              s.source_request_id, s.ingested_at AS source_freshness_at,
              sha2(to_json(named_struct(
                'open', s.open, 'high', s.high, 'low', s.low, 'close', s.close,
                'vwap', s.vwap, 'volume', s.volume, 'transactions', s.transactions,
                'daily_return', g.daily_return,
                'annualized_volatility_20d', g.annualized_volatility_20d,
                'source_request_id', s.source_request_id,
                'source_freshness_at', s.ingested_at
              )), 256) AS serving_content_hash
            FROM {silver} s
            INNER JOIN {gold} g USING (ticker, trading_date)"""


def publish_sql(catalog: str, schema: str) -> tuple[str, ...]:
    target = _qualified_name(catalog, schema, TARGET_TABLE)
    source = serving_source_sql(catalog, schema)
    return (
        f"""CREATE TABLE IF NOT EXISTS {target}
            TBLPROPERTIES (
              'delta.enableChangeDataFeed' = 'true',
              'delta.enableRowTracking' = 'true'
            )
            AS SELECT * FROM ({source}) WHERE false""",
        f"""ALTER TABLE {target} SET TBLPROPERTIES (
              'delta.enableChangeDataFeed' = 'true',
              'delta.enableRowTracking' = 'true'
            )""",
        f"""MERGE INTO {target} AS target
            USING ({source}) AS source
            ON target.ticker = source.ticker AND target.trading_date = source.trading_date
            WHEN MATCHED AND NOT (target.serving_content_hash <=> source.serving_content_hash)
              THEN UPDATE SET *
            WHEN NOT MATCHED THEN INSERT *
            WHEN NOT MATCHED BY SOURCE THEN DELETE""",
    )


def run(catalog: str, schema: str, spark_session: Any | None = None) -> dict[str, Any]:
    if spark_session is None:
        from pyspark.sql import SparkSession

        spark_session = SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()

    target = _qualified_name(catalog, schema, TARGET_TABLE)
    source = serving_source_sql(catalog, schema)
    for statement in publish_sql(catalog, schema):
        spark_session.sql(statement)

    counts = spark_session.sql(
        f"""SELECT
              (SELECT count(*) FROM ({source})) AS source_count,
              (SELECT count(*) FROM {target}) AS target_count,
              (SELECT count(*) - count(DISTINCT struct(ticker, trading_date)) FROM {target})
                AS duplicate_market_keys"""
    ).first()
    result = {
        "target": f"{catalog}.{schema}.{TARGET_TABLE}",
        "source_count": int(counts["source_count"]),
        "target_count": int(counts["target_count"]),
        "duplicate_market_keys": int(counts["duplicate_market_keys"]),
    }
    if result["source_count"] != result["target_count"] or result["duplicate_market_keys"]:
        raise RuntimeError(f"Market serving-table reconciliation failed: {result}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.catalog, args.schema), sort_keys=True))
    return 0


if __name__ == "__main__":
    main()
