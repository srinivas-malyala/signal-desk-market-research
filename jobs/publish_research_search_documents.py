"""Publish canonical research chunks to the stable Delta table used by AI Search."""

from __future__ import annotations

import argparse
import json
import re
from typing import Any

SOURCE_TABLE = "silver_research_chunks"
TARGET_TABLE = "research_search_documents"
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _qualified_name(catalog: str, schema: str, table: str) -> str:
    parts = (catalog, schema, table)
    if not all(_IDENTIFIER.fullmatch(part) for part in parts):
        raise ValueError("Catalog, schema, and table names must be simple SQL identifiers")
    return ".".join(f"`{part}`" for part in parts)


def publish_sql(catalog: str, schema: str) -> tuple[str, ...]:
    """Return the idempotent DDL/DML statements for the AI Search serving table."""
    source = _qualified_name(catalog, schema, SOURCE_TABLE)
    target = _qualified_name(catalog, schema, TARGET_TABLE)
    return (
        f"""CREATE TABLE IF NOT EXISTS {target}
            TBLPROPERTIES (
              'delta.enableChangeDataFeed' = 'true',
              'delta.enableRowTracking' = 'true'
            )
            AS SELECT * FROM {source} WHERE false""",
        f"""ALTER TABLE {target} SET TBLPROPERTIES (
              'delta.enableChangeDataFeed' = 'true',
              'delta.enableRowTracking' = 'true'
            )""",
        f"""MERGE INTO {target} AS target
            USING {source} AS source
            ON target.chunk_id = source.chunk_id
            WHEN MATCHED AND NOT (
              target.chunk_content_hash <=> source.chunk_content_hash
              AND target.source_content_hash <=> source.source_content_hash
              AND target.tickers <=> source.tickers
              AND target.title <=> source.title
              AND target.source_date <=> source.source_date
              AND target.source_url <=> source.source_url
              AND target.fetched_at <=> source.fetched_at
            ) THEN UPDATE SET *
            WHEN NOT MATCHED THEN INSERT *
            WHEN NOT MATCHED BY SOURCE THEN DELETE""",
    )


def run(catalog: str, schema: str, spark_session: Any | None = None) -> dict[str, Any]:
    if spark_session is None:
        from pyspark.sql import SparkSession

        spark_session = SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()

    source = _qualified_name(catalog, schema, SOURCE_TABLE)
    target = _qualified_name(catalog, schema, TARGET_TABLE)
    for statement in publish_sql(catalog, schema):
        spark_session.sql(statement)

    counts = spark_session.sql(
        f"""SELECT
              (SELECT count(*) FROM {source}) AS source_count,
              (SELECT count(*) FROM {target}) AS target_count,
              (SELECT count(*) - count(DISTINCT chunk_id) FROM {target}) AS duplicate_chunk_ids"""
    ).first()
    result = {
        "source": f"{catalog}.{schema}.{SOURCE_TABLE}",
        "target": f"{catalog}.{schema}.{TARGET_TABLE}",
        "source_count": int(counts["source_count"]),
        "target_count": int(counts["target_count"]),
        "duplicate_chunk_ids": int(counts["duplicate_chunk_ids"]),
    }
    if result["source_count"] != result["target_count"] or result["duplicate_chunk_ids"]:
        raise RuntimeError(f"AI Search serving-table reconciliation failed: {result}")
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
