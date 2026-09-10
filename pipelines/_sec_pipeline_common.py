"""Shared SEC schemas and Volume configuration for Spark Declarative Pipelines."""

from pyspark.sql import types as T

SEC_MANIFEST_SCHEMA = T.StructType(
    [
        T.StructField("version", T.IntegerType()),
        T.StructField("source", T.StringType()),
        T.StructField("kind", T.StringType()),
        T.StructField("ticker", T.StringType()),
        T.StructField("cik", T.StringType()),
        T.StructField("accession_number", T.StringType()),
        T.StructField("form", T.StringType()),
        T.StructField("filing_date", T.StringType()),
        T.StructField("report_date", T.StringType()),
        T.StructField("acceptance_datetime", T.StringType()),
        T.StructField("primary_document", T.StringType()),
        T.StructField("primary_doc_description", T.StringType()),
        T.StructField("source_url", T.StringType()),
        T.StructField("content_type", T.StringType()),
        T.StructField("status_code", T.IntegerType()),
        T.StructField("byte_count", T.LongType()),
        T.StructField("checksum_sha256", T.StringType()),
        T.StructField("fetched_at", T.StringType()),
        T.StructField("landing_path", T.StringType()),
        T.StructField("_rescued_data", T.StringType()),
    ]
)

SEC_RECENT_FILINGS_SCHEMA = T.StructType(
    [
        T.StructField("accessionNumber", T.ArrayType(T.StringType())),
        T.StructField("filingDate", T.ArrayType(T.StringType())),
        T.StructField("reportDate", T.ArrayType(T.StringType())),
        T.StructField("acceptanceDateTime", T.ArrayType(T.StringType())),
        T.StructField("act", T.ArrayType(T.StringType())),
        T.StructField("form", T.ArrayType(T.StringType())),
        T.StructField("fileNumber", T.ArrayType(T.StringType())),
        T.StructField("filmNumber", T.ArrayType(T.StringType())),
        T.StructField("items", T.ArrayType(T.StringType())),
        T.StructField("size", T.ArrayType(T.LongType())),
        T.StructField("isXBRL", T.ArrayType(T.IntegerType())),
        T.StructField("isInlineXBRL", T.ArrayType(T.IntegerType())),
        T.StructField("primaryDocument", T.ArrayType(T.StringType())),
        T.StructField("primaryDocDescription", T.ArrayType(T.StringType())),
    ]
)

SEC_SUBMISSIONS_SCHEMA = T.StructType(
    [
        T.StructField("cik", T.StringType()),
        T.StructField("entityType", T.StringType()),
        T.StructField("sic", T.StringType()),
        T.StructField("sicDescription", T.StringType()),
        T.StructField("name", T.StringType()),
        T.StructField("tickers", T.ArrayType(T.StringType())),
        T.StructField("exchanges", T.ArrayType(T.StringType())),
        T.StructField("ein", T.StringType()),
        T.StructField("description", T.StringType()),
        T.StructField("website", T.StringType()),
        T.StructField("investorWebsite", T.StringType()),
        T.StructField("category", T.StringType()),
        T.StructField("fiscalYearEnd", T.StringType()),
        T.StructField("stateOfIncorporation", T.StringType()),
        T.StructField(
            "filings",
            T.StructType(
                [
                    T.StructField("recent", SEC_RECENT_FILINGS_SCHEMA),
                    T.StructField("files", T.ArrayType(T.MapType(T.StringType(), T.StringType()))),
                ]
            ),
        ),
        T.StructField("_rescued_data", T.StringType()),
    ]
)

SEC_FACT_OBSERVATION_SCHEMA = T.StructType(
    [
        T.StructField("start", T.StringType()),
        T.StructField("end", T.StringType()),
        T.StructField("val", T.StringType()),
        T.StructField("accn", T.StringType()),
        T.StructField("fy", T.LongType()),
        T.StructField("fp", T.StringType()),
        T.StructField("form", T.StringType()),
        T.StructField("filed", T.StringType()),
        T.StructField("frame", T.StringType()),
    ]
)

SEC_CONCEPT_SCHEMA = T.StructType(
    [
        T.StructField("label", T.StringType()),
        T.StructField("description", T.StringType()),
        T.StructField(
            "units",
            T.MapType(T.StringType(), T.ArrayType(SEC_FACT_OBSERVATION_SCHEMA)),
        ),
    ]
)

SEC_COMPANY_FACTS_SCHEMA = T.StructType(
    [
        T.StructField("cik", T.LongType()),
        T.StructField("entityName", T.StringType()),
        T.StructField(
            "facts",
            T.MapType(T.StringType(), T.MapType(T.StringType(), SEC_CONCEPT_SCHEMA)),
        ),
        T.StructField("_rescued_data", T.StringType()),
    ]
)


def raw_sec_path(spark) -> str:
    return f"{spark.conf.get('signal_desk.raw_volume_path').rstrip('/')}/sec"
