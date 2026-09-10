"""Incrementally ingest all immutable SEC landing manifests."""

from _sec_pipeline_common import SEC_MANIFEST_SCHEMA, raw_sec_path
from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.table(
    name="bronze_sec_manifests",
    comment="Immutable SEC provenance for submissions, Company Facts, and filing documents.",
    cluster_by=["kind", "cik"],
    table_properties={"delta.enableRowTracking": "true"},
)
@dp.expect_all_or_fail(
    {
        "manifest_version_supported": "version = 1",
        "manifest_source_supported": "source = 'sec_edgar'",
        "official_source_url": "source_url RLIKE '^https://(data|www)[.]sec[.]gov/'",
        "valid_cik": "cik RLIKE '^[0-9]{10}$'",
        "successful_response": "status_code = 200",
        "valid_checksum": "checksum_sha256 RLIKE '^[a-f0-9]{64}$'",
        "manifest_not_rescued": "rescued_data IS NULL",
    }
)
def bronze_sec_manifests():
    return (
        spark.readStream.format("cloudFiles")  # noqa: F821 - injected by Databricks SDP
        .option("cloudFiles.format", "json")
        .option("cloudFiles.schemaEvolutionMode", "rescue")
        .option("cloudFiles.includeExistingFiles", "true")
        .option("rescuedDataColumn", "_rescued_data")
        .option("recursiveFileLookup", "true")
        .option("pathGlobFilter", "manifest.json")
        .schema(SEC_MANIFEST_SCHEMA)
        .load(raw_sec_path(spark))  # noqa: F821 - injected by Databricks SDP
        .select(
            "version",
            "source",
            "kind",
            F.upper("ticker").alias("ticker"),
            F.lpad(F.col("cik").cast("string"), 10, "0").alias("cik"),
            "accession_number",
            "form",
            F.to_date("filing_date").alias("filing_date"),
            F.to_date("report_date").alias("report_date"),
            F.to_timestamp("acceptance_datetime").alias("acceptance_datetime"),
            "primary_document",
            "primary_doc_description",
            "source_url",
            "content_type",
            "status_code",
            "byte_count",
            "checksum_sha256",
            F.to_timestamp("fetched_at").alias("fetched_at"),
            "landing_path",
            F.col("_metadata.file_path").alias("manifest_path"),
            F.current_timestamp().alias("ingested_at"),
            F.col("_rescued_data").alias("rescued_data"),
        )
    )
