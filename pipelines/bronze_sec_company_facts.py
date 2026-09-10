"""Incrementally ingest dynamic SEC Company Facts taxonomy maps."""

from _sec_pipeline_common import SEC_COMPANY_FACTS_SCHEMA, raw_sec_path
from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.table(
    name="bronze_sec_company_facts",
    comment="Raw SEC Company Facts snapshots preserving arbitrary taxonomies, concepts, and units.",
    cluster_by=["cik"],
    table_properties={"delta.enableRowTracking": "true"},
)
@dp.expect_all_or_fail(
    {
        "valid_cik": "cik RLIKE '^[0-9]{10}$'",
        "entity_name_present": "entity_name IS NOT NULL",
        "facts_present": "facts IS NOT NULL",
    }
)
def bronze_sec_company_facts():
    return (
        spark.readStream.format("cloudFiles")  # noqa: F821 - injected by Databricks SDP
        .option("cloudFiles.format", "json")
        .option("cloudFiles.schemaEvolutionMode", "rescue")
        .option("cloudFiles.includeExistingFiles", "true")
        .option("rescuedDataColumn", "_rescued_data")
        .option("recursiveFileLookup", "true")
        .option("pathGlobFilter", "response.json")
        .schema(SEC_COMPANY_FACTS_SCHEMA)
        .load(f"{raw_sec_path(spark)}/companyfacts")  # noqa: F821 - injected by Databricks SDP
        .select(
            F.lpad(F.col("cik").cast("string"), 10, "0").alias("cik"),
            F.col("entityName").alias("entity_name"),
            "facts",
            F.col("_metadata.file_path").alias("source_path"),
            F.regexp_extract(F.col("_metadata.file_path"), r"checksum=([a-f0-9]{64})", 1).alias(
                "checksum_sha256"
            ),
            F.current_timestamp().alias("ingested_at"),
            F.col("_rescued_data").alias("rescued_data"),
        )
    )
