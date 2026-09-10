"""Incrementally ingest content-addressed SEC submissions snapshots."""

from _sec_pipeline_common import SEC_SUBMISSIONS_SCHEMA, raw_sec_path
from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.table(
    name="bronze_sec_submissions",
    comment="Raw SEC company submissions snapshots with schema-drift rescue and file lineage.",
    cluster_by=["cik"],
    table_properties={"delta.enableRowTracking": "true"},
)
@dp.expect_all_or_fail(
    {
        "valid_cik": "cik RLIKE '^[0-9]{10}$'",
        "company_name_present": "company_name IS NOT NULL",
        "source_path_present": "source_path IS NOT NULL",
    }
)
def bronze_sec_submissions():
    return (
        spark.readStream.format("cloudFiles")  # noqa: F821 - injected by Databricks SDP
        .option("cloudFiles.format", "json")
        .option("cloudFiles.schemaEvolutionMode", "rescue")
        .option("cloudFiles.includeExistingFiles", "true")
        .option("rescuedDataColumn", "_rescued_data")
        .option("recursiveFileLookup", "true")
        .option("pathGlobFilter", "response.json")
        .schema(SEC_SUBMISSIONS_SCHEMA)
        .load(f"{raw_sec_path(spark)}/submissions")  # noqa: F821 - injected by Databricks SDP
        .select(
            F.lpad(F.col("cik").cast("string"), 10, "0").alias("cik"),
            F.col("name").alias("company_name"),
            F.col("entityType").alias("entity_type"),
            "sic",
            F.col("sicDescription").alias("sic_description"),
            "tickers",
            "exchanges",
            "ein",
            "description",
            "website",
            F.col("investorWebsite").alias("investor_website"),
            "category",
            F.col("fiscalYearEnd").alias("fiscal_year_end"),
            F.col("stateOfIncorporation").alias("state_of_incorporation"),
            "filings",
            F.col("_metadata.file_path").alias("source_path"),
            F.regexp_extract(F.col("_metadata.file_path"), r"checksum=([a-f0-9]{64})", 1).alias(
                "checksum_sha256"
            ),
            F.current_timestamp().alias("ingested_at"),
            F.col("_rescued_data").alias("rescued_data"),
        )
    )
