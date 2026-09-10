"""Incrementally parse immutable SEC filing HTML into normalized text."""

from document_text import normalized_filing
from pyspark import pipelines as dp
from pyspark.sql import functions as F
from pyspark.sql import types as T

PARSED_DOCUMENT_SCHEMA = T.StructType(
    [
        T.StructField("document_text", T.StringType()),
        T.StructField("selected_sections", T.ArrayType(T.StringType())),
    ]
)
parse_document = F.udf(normalized_filing, PARSED_DOCUMENT_SCHEMA)


@dp.table(
    name="bronze_sec_filing_documents",
    comment="Normalized text and section metadata derived from immutable SEC filing HTML.",
    cluster_by=["cik", "accession_number"],
    table_properties={"delta.enableRowTracking": "true"},
)
@dp.expect_all_or_fail(
    {
        "valid_cik": "cik RLIKE '^[0-9]{10}$'",
        "valid_accession": "accession_number RLIKE '^[0-9]{10}-[0-9]{2}-[0-9]{6}$'",
        "source_path_present": "source_path IS NOT NULL",
        "content_hash_present": "source_content_hash RLIKE '^[a-f0-9]{64}$'",
    }
)
@dp.expect("document_text_present", "length(document_text) > 0")
def bronze_sec_filing_documents():
    documents = (
        spark.readStream.format("cloudFiles")  # noqa: F821 - injected by Databricks SDP
        .option("cloudFiles.format", "binaryFile")
        .option("cloudFiles.includeExistingFiles", "true")
        .option("recursiveFileLookup", "true")
        .option("pathGlobFilter", "document.html")
        .load(f"{spark.conf.get('signal_desk.raw_volume_path').rstrip('/')}/sec/filings")  # noqa: F821
    )
    parsed = parse_document(F.decode("content", "UTF-8"))
    return documents.select(
        F.regexp_extract(F.col("_metadata.file_path"), r"cik=([0-9]{10})", 1).alias("cik"),
        F.regexp_extract(
            F.col("_metadata.file_path"),
            r"accession=([0-9]{10}-[0-9]{2}-[0-9]{6})",
            1,
        ).alias("accession_number"),
        F.col("_metadata.file_path").alias("source_path"),
        F.col("length").alias("byte_count"),
        F.sha2("content", 256).alias("source_content_hash"),
        parsed.document_text.alias("document_text"),
        parsed.selected_sections.alias("selected_sections"),
        F.current_timestamp().alias("ingested_at"),
    )
