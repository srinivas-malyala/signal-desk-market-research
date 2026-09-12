"""Deduplicate effective Lakebase operations into safe agent activity history."""

from pyspark import pipelines as dp
from pyspark.sql import Window
from pyspark.sql import functions as F


@dp.materialized_view(
    name="silver_agent_activity",
    comment="Effective, deduplicated operational activity without direct identity or authored research text.",
    cluster_by=["activity_date", "source_table", "tool_name"],
    table_properties={"delta.enableRowTracking": "true", "delta.enableChangeDataFeed": "true"},
)
@dp.expect_all_or_fail(
    {
        "effective_change": "change_type IN ('insert','update_postimage','delete')",
        "valid_status": "status IS NULL OR status IN ('success','error','active','completed','failed')",
        "valid_duration": "duration_ms IS NULL OR duration_ms >= 0",
        "direct_identity_absent": "user_pseudonym IS NULL OR length(user_pseudonym) = 64",
    }
)
def silver_agent_activity():
    changes = spark.read.table("bronze_lakebase_changes").filter(  # noqa: F821
        F.col("change_type").isin("insert", "update_postimage", "delete")
    )
    latest_duplicate = Window.partitionBy("change_id").orderBy(
        F.col("sort_by").desc(),
        F.col("synced_at").desc(),
    )
    return (
        changes.withColumn("duplicate_rank", F.row_number().over(latest_duplicate))
        .filter(F.col("duplicate_rank") == 1)
        .withColumn("activity_date", F.to_date("event_timestamp"))
        .withColumn("source_latency_seconds", F.unix_timestamp("synced_at") - F.unix_timestamp("event_timestamp"))
        .select(
            "change_id",
            "source_table",
            "record_key",
            "change_type",
            "pg_lsn",
            "pg_xid",
            "sort_by",
            "synced_at",
            "event_timestamp",
            "activity_date",
            "source_latency_seconds",
            "user_pseudonym",
            "session_id",
            "tool_name",
            "status",
            "duration_ms",
            "action_type",
        )
    )
