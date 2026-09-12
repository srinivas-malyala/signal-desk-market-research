"""Normalize selected Lakehouse Sync history tables into one safe CDC stream."""

from _activity_pipeline_common import cdc_action, common_metadata, history_table, user_pseudonym
from pyspark import pipelines as dp
from pyspark.sql import functions as F

NORMALIZED_SCHEMA = """
change_id STRING NOT NULL,
source_table STRING NOT NULL,
record_key STRING NOT NULL,
change_type STRING NOT NULL,
pg_lsn BIGINT NOT NULL,
pg_xid BIGINT,
sort_by BIGINT NOT NULL,
synced_at TIMESTAMP NOT NULL,
event_timestamp TIMESTAMP NOT NULL,
user_pseudonym STRING,
session_id STRING,
tool_name STRING,
status STRING,
duration_ms BIGINT,
action_type STRING NOT NULL
"""

dp.create_streaming_table(
    name="bronze_lakebase_changes",
    comment="Safe, normalized CDC operations from selected Lakebase history tables.",
    schema=NORMALIZED_SCHEMA,
    cluster_by=["source_table", "event_timestamp"],
    table_properties={"delta.enableRowTracking": "true"},
    expect_all_or_drop={
        "known_change_type": "change_type IN ('insert','update_preimage','update_postimage','delete')",
        "valid_lsn": "pg_lsn >= 0",
        "valid_sort_key": "sort_by >= 0",
        "event_time_present": "event_timestamp IS NOT NULL",
    },
)


@dp.append_flow(target="bronze_lakebase_changes", name="agent_tool_events_cdc")
def agent_tool_events_cdc():
    changes = spark.readStream.table(history_table(spark, "agent_tool_events"))  # noqa: F821
    key = F.col("event_id").cast("string")
    change_type = F.col("_pg_change_type")
    return changes.select(
        *common_metadata("agent_tool_events", key),
        F.when(change_type == "delete", F.col("_timestamp"))
        .otherwise(F.col("created_at"))
        .cast("timestamp")
        .alias("event_timestamp"),
        user_pseudonym(F.col("user_id")).alias("user_pseudonym"),
        F.col("session_id").cast("string").alias("session_id"),
        F.col("tool_name").cast("string").alias("tool_name"),
        F.col("status").cast("string").alias("status"),
        F.col("duration_ms").cast("long").alias("duration_ms"),
        F.col("action_type").cast("string").alias("action_type"),
    )


@dp.append_flow(target="bronze_lakebase_changes", name="agent_sessions_cdc")
def agent_sessions_cdc():
    changes = spark.readStream.table(history_table(spark, "agent_sessions"))  # noqa: F821
    key = F.col("session_id").cast("string")
    change_type = F.col("_pg_change_type")
    return changes.select(
        *common_metadata("agent_sessions", key),
        F.when(change_type == "insert", F.col("created_at"))
        .when(change_type == "update_postimage", F.col("last_activity_at"))
        .otherwise(F.col("_timestamp"))
        .cast("timestamp")
        .alias("event_timestamp"),
        user_pseudonym(F.col("user_id")).alias("user_pseudonym"),
        key.alias("session_id"),
        F.lit(None).cast("string").alias("tool_name"),
        F.col("status").cast("string").alias("status"),
        F.lit(None).cast("long").alias("duration_ms"),
        cdc_action(change_type, insert_action="create").alias("action_type"),
    )


@dp.append_flow(target="bronze_lakebase_changes", name="watchlist_tickers_cdc")
def watchlist_tickers_cdc():
    changes = spark.readStream.table(history_table(spark, "watchlist_tickers"))  # noqa: F821
    key = F.concat_ws(":", F.col("watchlist_id").cast("string"), F.col("ticker").cast("string"))
    change_type = F.col("_pg_change_type")
    return changes.select(
        *common_metadata("watchlist_tickers", key),
        F.when(change_type == "delete", F.col("_timestamp"))
        .otherwise(F.coalesce(F.col("last_viewed_at"), F.col("added_at"), F.col("_timestamp")))
        .cast("timestamp")
        .alias("event_timestamp"),
        F.lit(None).cast("string").alias("user_pseudonym"),
        F.lit(None).cast("string").alias("session_id"),
        F.lit("update_watchlist").alias("tool_name"),
        F.lit("success").alias("status"),
        F.lit(None).cast("long").alias("duration_ms"),
        cdc_action(change_type, insert_action="create").alias("action_type"),
    )


@dp.append_flow(target="bronze_lakebase_changes", name="research_notes_cdc")
def research_notes_cdc():
    changes = spark.readStream.table(history_table(spark, "research_notes"))  # noqa: F821
    key = F.col("id").cast("string")
    change_type = F.col("_pg_change_type")
    return changes.select(
        *common_metadata("research_notes", key),
        F.when(change_type == "delete", F.col("_timestamp"))
        .otherwise(F.coalesce(F.col("updated_at"), F.col("created_at"), F.col("_timestamp")))
        .cast("timestamp")
        .alias("event_timestamp"),
        user_pseudonym(F.col("user_id")).alias("user_pseudonym"),
        F.lit(None).cast("string").alias("session_id"),
        F.lit("save_research_note").alias("tool_name"),
        F.lit("success").alias("status"),
        F.lit(None).cast("long").alias("duration_ms"),
        cdc_action(change_type, insert_action="create").alias("action_type"),
    )


@dp.append_flow(target="bronze_lakebase_changes", name="analysis_reports_cdc")
def analysis_reports_cdc():
    changes = spark.readStream.table(history_table(spark, "analysis_reports"))  # noqa: F821
    key = F.col("id").cast("string")
    change_type = F.col("_pg_change_type")
    return changes.select(
        *common_metadata("analysis_reports", key),
        F.when(change_type == "delete", F.col("_timestamp"))
        .otherwise(F.coalesce(F.col("created_at"), F.col("_timestamp")))
        .cast("timestamp")
        .alias("event_timestamp"),
        user_pseudonym(F.col("user_id")).alias("user_pseudonym"),
        F.lit(None).cast("string").alias("session_id"),
        F.lit("save_analysis_report").alias("tool_name"),
        F.lit("success").alias("status"),
        F.lit(None).cast("long").alias("duration_ms"),
        cdc_action(change_type, insert_action="create").alias("action_type"),
    )
