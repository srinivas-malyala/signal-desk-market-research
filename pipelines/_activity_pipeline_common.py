"""Shared contracts for Lakebase CDC activity analytics."""

from __future__ import annotations

from pyspark.sql import Column, SparkSession
from pyspark.sql import functions as F

CDC_CHANGE_TYPES = ("insert", "update_preimage", "update_postimage", "delete")
CDC_SOURCE_TABLES = (
    "agent_tool_events",
    "agent_sessions",
    "watchlist_tickers",
    "research_notes",
    "analysis_reports",
)


def history_table(spark_session: SparkSession, base_name: str) -> str:
    """Return the configured fully qualified Lakehouse Sync history table."""
    if base_name not in CDC_SOURCE_TABLES:
        raise ValueError(f"Unsupported Lakebase CDC source: {base_name}")
    catalog = spark_session.conf.get("signal_desk.cdc_source_catalog")
    schema = spark_session.conf.get("signal_desk.cdc_source_schema")
    suffix = spark_session.conf.get("signal_desk.lakebase_table_suffix")
    return f"{catalog}.{schema}.lb_{base_name}_{suffix}_history"


def user_pseudonym(user_id: Column) -> Column:
    """Create a stable pseudonym without publishing the Lakebase identifier."""
    return F.when(
        user_id.isNotNull(),
        F.sha2(F.concat(F.lit("signal-desk-lakebase-user:"), user_id.cast("string")), 256),
    )


def cdc_action(change_type: Column, *, insert_action: str) -> Column:
    """Map the effective CDC operation to an analytics action."""
    return (
        F.when(change_type == "insert", F.lit(insert_action))
        .when(change_type == "update_postimage", F.lit("update"))
        .when(change_type == "delete", F.lit("delete"))
        .otherwise(F.lit("update_preimage"))
    )


def change_id(source_table: str, record_key: Column, change_type: Column, pg_lsn: Column) -> Column:
    """Build an idempotent identity for one source-row CDC operation."""
    return F.sha2(
        F.concat_ws(
            "||",
            F.lit(source_table),
            record_key,
            change_type,
            pg_lsn.cast("string"),
        ),
        256,
    )


def common_metadata(source_table: str, record_key: Column) -> list[Column]:
    """Select and type the Lakehouse Sync metadata shared by every flow."""
    change_type = F.col("_pg_change_type").cast("string")
    pg_lsn = F.col("_pg_lsn").cast("long")
    return [
        change_id(source_table, record_key, change_type, pg_lsn).alias("change_id"),
        F.lit(source_table).alias("source_table"),
        record_key.cast("string").alias("record_key"),
        change_type.alias("change_type"),
        pg_lsn.alias("pg_lsn"),
        F.col("_pg_xid").cast("long").alias("pg_xid"),
        F.col("_sort_by").cast("long").alias("sort_by"),
        F.col("_timestamp").cast("timestamp").alias("synced_at"),
    ]
