"""Atomically publish bounded Unity Catalog serving copies into shared Lakebase tables."""

from __future__ import annotations

import argparse
import base64
import json
import re
from collections.abc import Iterable
from typing import Any

from databricks.sdk import WorkspaceClient
from psycopg2 import connect, sql
from psycopg2.extras import execute_values

MARKET_COLUMNS = (
    "ticker",
    "trading_date",
    "open",
    "high",
    "low",
    "close",
    "vwap",
    "volume",
    "transactions",
    "daily_return",
    "annualized_volatility_20d",
    "source_request_id",
    "source_freshness_at",
    "serving_content_hash",
)
RESEARCH_COLUMNS = (
    "chunk_id",
    "parent_id",
    "source_type",
    "source_id",
    "tickers_text",
    "ticker",
    "title",
    "source_date",
    "source_url",
    "fetched_at",
    "section_name",
    "chunk_index",
    "chunk_to_retrieve",
    "chunk_token_count",
    "parent_text",
    "parent_token_count",
    "source_content_hash",
)
IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


def _identifier(value: str, label: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase SQL identifier")
    return value


def serving_tables(suffix: str) -> tuple[str, str]:
    clean_suffix = _identifier(suffix, "suffix")
    return f"market_history_serving_{clean_suffix}", f"research_documents_serving_{clean_suffix}"


def research_source_sql(catalog: str, schema: str) -> str:
    for value, label in ((catalog, "catalog"), (schema, "schema")):
        _identifier(value, label)
    return f"""SELECT chunk_id, parent_id, source_type, source_id,
              CASE WHEN tickers IS NULL OR size(tickers) = 0 THEN ''
                   ELSE concat('|', concat_ws('|', transform(tickers, value -> upper(value))), '|')
              END AS tickers_text,
              ticker, title, source_date, source_url, fetched_at, section_name, chunk_index,
              chunk_to_retrieve, chunk_token_count, parent_text, parent_token_count,
              source_content_hash
            FROM `{catalog}`.`{schema}`.`research_search_documents`"""


def _row_tuples(rows: Iterable[Any], columns: tuple[str, ...]) -> Iterable[tuple[Any, ...]]:
    for row in rows:
        yield tuple(row[column] for column in columns)


def _load_temp_table(cursor, temp_table: str, columns: tuple[str, ...], rows: Iterable[Any]) -> int:
    insert = sql.SQL("INSERT INTO {} ({}) VALUES %s").format(
        sql.Identifier(temp_table),
        sql.SQL(", ").join(map(sql.Identifier, columns)),
    )
    loaded = 0
    batch: list[tuple[Any, ...]] = []
    for values in _row_tuples(rows, columns):
        batch.append(values)
        if len(batch) == 2_000:
            execute_values(cursor, insert.as_string(cursor), batch, page_size=len(batch))
            loaded += len(batch)
            batch.clear()
    if batch:
        execute_values(cursor, insert.as_string(cursor), batch, page_size=len(batch))
        loaded += len(batch)
    return loaded


def _replace_from_temp(
    cursor,
    schema: str,
    target: str,
    temp_table: str,
    columns: tuple[str, ...],
    key_columns: tuple[str, ...],
    expected_count: int,
) -> None:
    cursor.execute(
        sql.SQL("SELECT count(*), count(*) - count(DISTINCT ({})) FROM {}").format(
            sql.SQL(", ").join(map(sql.Identifier, key_columns)),
            sql.Identifier(temp_table),
        )
    )
    actual_count, duplicates = cursor.fetchone()
    if int(actual_count) != expected_count or int(duplicates):
        raise RuntimeError(
            f"Lakebase staging reconciliation failed for {target}: "
            f"expected={expected_count}, actual={actual_count}, duplicates={duplicates}"
        )
    qualified_target = sql.SQL("{}.{}").format(sql.Identifier(schema), sql.Identifier(target))
    cursor.execute(sql.SQL("LOCK TABLE {} IN ACCESS EXCLUSIVE MODE").format(qualified_target))
    cursor.execute(sql.SQL("TRUNCATE TABLE {}").format(qualified_target))
    cursor.execute(
        sql.SQL("INSERT INTO {} ({}) SELECT {} FROM {}").format(
            qualified_target,
            sql.SQL(", ").join(map(sql.Identifier, columns)),
            sql.SQL(", ").join(map(sql.Identifier, columns)),
            sql.Identifier(temp_table),
        )
    )


def run(
    catalog: str,
    schema: str,
    pg_schema: str,
    suffix: str,
    secret_scope: str,
    secret_key: str,
    dataset: str = "both",
    spark_session: Any | None = None,
    workspace_client: Any | None = None,
) -> dict[str, Any]:
    """Stream selected serving datasets into session-local staging and commit atomically."""

    clean_pg_schema = _identifier(pg_schema, "pg_schema")
    market_table, research_table = serving_tables(suffix)
    if dataset not in {"market", "research", "both"}:
        raise ValueError("dataset must be market, research, or both")
    for value, label in ((catalog, "catalog"), (schema, "schema")):
        _identifier(value, label)
    if spark_session is None:
        from pyspark.sql import SparkSession

        spark_session = SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
    workspace_client = workspace_client or WorkspaceClient()
    secret = workspace_client.secrets.get_secret(scope=secret_scope, key=secret_key)
    dsn = base64.b64decode(secret.value).decode("utf-8")

    connection = connect(dsn, connect_timeout=15, application_name="signal-desk-serving-publisher")
    published: dict[str, int] = {}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '60min'")
            if dataset in {"market", "both"}:
                market_source = f"`{catalog}`.`{schema}`.`market_history_serving`"
                market_frame = spark_session.table(market_source).select(*MARKET_COLUMNS)
                temp_market = f"market_history_load_{suffix}"
                cursor.execute(
                    sql.SQL("CREATE TEMP TABLE {} (LIKE {}.{} INCLUDING DEFAULTS) ON COMMIT DROP").format(
                        sql.Identifier(temp_market),
                        sql.Identifier(clean_pg_schema),
                        sql.Identifier(market_table),
                    )
                )
                market_count = _load_temp_table(
                    cursor, temp_market, MARKET_COLUMNS, market_frame.toLocalIterator()
                )
                _replace_from_temp(
                    cursor,
                    clean_pg_schema,
                    market_table,
                    temp_market,
                    MARKET_COLUMNS,
                    ("ticker", "trading_date"),
                    market_count,
                )
                published[market_table] = market_count

            if dataset in {"research", "both"}:
                research_frame = spark_session.sql(research_source_sql(catalog, schema)).select(
                    *RESEARCH_COLUMNS
                )
                temp_research = f"research_documents_load_{suffix}"
                cursor.execute(
                    sql.SQL("CREATE TEMP TABLE {} (LIKE {}.{} INCLUDING DEFAULTS) ON COMMIT DROP").format(
                        sql.Identifier(temp_research),
                        sql.Identifier(clean_pg_schema),
                        sql.Identifier(research_table),
                    )
                )
                research_count = _load_temp_table(
                    cursor, temp_research, RESEARCH_COLUMNS, research_frame.toLocalIterator()
                )
                _replace_from_temp(
                    cursor,
                    clean_pg_schema,
                    research_table,
                    temp_research,
                    RESEARCH_COLUMNS,
                    ("chunk_id",),
                    research_count,
                )
                published[research_table] = research_count
        connection.commit()
        return {
            "source_catalog_schema": f"{catalog}.{schema}",
            "target_schema": clean_pg_schema,
            "dataset": dataset,
            "tables": published,
            "publish_mode": "atomic_temp_stage_replace",
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--pg-schema", default="bootcamp_students")
    parser.add_argument("--suffix", default="srini")
    parser.add_argument("--secret-scope", default="database")
    parser.add_argument("--secret-key", default="lakebase-url")
    parser.add_argument("--dataset", choices=("market", "research", "both"), default="both")
    args = parser.parse_args()
    print(json.dumps(run(**vars(args)), sort_keys=True))
    return 0


if __name__ == "__main__":
    main()
